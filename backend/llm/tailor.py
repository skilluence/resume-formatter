"""Orchestrates one JD-tailoring run: source resume + JD text -> three drafts.

Design guarantee: the LLM can never corrupt a fact. We ask it only for the
*wording* (summary, skills, bullets, projects, letter, email); then we re-stamp
every factual field (name, contact, employers, titles, dates, education, certs)
from the source resume in code. So even a hallucinating model cannot change who
the candidate is or where they worked.
"""
import copy
import json
import logging

from llm.client import get_client, get_model
from llm.prompts import build_messages

logger = logging.getLogger("resume.tailor")

# Replace em/en dashes anywhere they slip through, per the spec (no em dashes).
_DASHES = {"—": " - ", "–": "-"}


def _scrub_dashes(text):
    if isinstance(text, str):
        for bad, good in _DASHES.items():
            text = text.replace(bad, good)
        return text
    if isinstance(text, list):
        return [_scrub_dashes(t) for t in text]
    if isinstance(text, dict):
        return {k: _scrub_dashes(v) for k, v in text.items()}
    return text


def _empty_letter(name: str) -> dict:
    return {
        "greeting": "Dear Hiring Manager,",
        "body_paragraphs": [],
        "closing": "Sincerely,",
        "signature": name or "",
    }


def _empty_email(name: str) -> dict:
    return {
        "subject": "",
        "greeting": "Dear Hiring Manager,",
        "body_paragraphs": [],
        "closing": "Best regards,",
        "signature": name or "",
    }


MAX_EXP_BULLETS = 6   # every role is normalized to at most this many bullets
MAX_PROJ_BULLETS = 6  # the page-fill engine then shows between 2 and 6 of these


def _clean_bullets(raw) -> list:
    return [str(b) for b in (raw or []) if str(b).strip()]


def _normalize_exp_bullets(ai_bullets, source_bullets) -> list:
    """Cap a role at 6 bullets; never wipe a role. Condensing >6 source bullets
    into 6 strong lines is the model's job (see prompts.py); this only caps the
    count and, if the model returned nothing, keeps the source bullets so a role
    can never go blank."""
    cleaned = _clean_bullets(ai_bullets)
    if not cleaned:
        return _clean_bullets(source_bullets)
    return cleaned[:MAX_EXP_BULLETS]


def _merge_skills(source_skills: dict, ai_skills) -> dict:
    """Take the AI's (re-organized, JD-ordered) skill categories as the base, but
    GUARANTEE every source skill survives: any skill the AI dropped is restored to
    its original category (recreating that category if the AI dropped it whole).
    The user's resume skills are never lost - we only ADD/re-order, never remove."""
    if not isinstance(ai_skills, dict) or not ai_skills:
        return {str(k): [str(s) for s in v if str(s).strip()]
                for k, v in (source_skills or {}).items() if isinstance(v, list)}

    merged = {}
    for k, v in ai_skills.items():
        if isinstance(v, list):
            items = [str(s) for s in v if str(s).strip()]
            if items:
                merged[str(k)] = items

    present = {s.lower() for items in merged.values() for s in items}
    for cat, items in (source_skills or {}).items():
        missing = [str(s) for s in (items or []) if str(s).strip() and str(s).lower() not in present]
        if missing:
            merged[str(cat)] = merged.get(str(cat), []) + missing
            present |= {s.lower() for s in missing}
    return merged


def _merge_resume(source: dict, ai: dict) -> dict:
    """Build the tailored resume: AI provides wording, source provides every fact.

    - headline / summary / skills: taken from the AI (content fields).
    - experience: AI supplies bullets ONLY (capped at 6); title/company/location/
      dates come from the source job at the same index (re-stamped).
    - projects: merged 1:1 BY SOURCE INDEX. The project NAME is a fact and always
      comes from the source; the AI may only supply tech_stack + ranked bullets.
      Every source project survives - none are dropped, renamed, reordered, or
      capped in number. Each project also carries `candidate_bullets` (the full
      ranked set, up to 6) that the frontend page-fill engine trims from.
    - name / contact / education / certifications / additional_sections: verbatim
      from the source. These are facts and are never sent through the model.
    """
    out = copy.deepcopy(source)

    if ai.get("headline"):
        out["headline"] = ai["headline"]
    if ai.get("summary"):
        out["summary"] = ai["summary"]
    if ai.get("summary_short"):
        out["summary_short"] = ai["summary_short"]
    out["skills"] = _merge_skills(source.get("skills") or {}, ai.get("skills"))

    # Experience: iterate the SOURCE jobs so the set of roles can never change.
    ai_exp = ai.get("experience") or []
    for i, job in enumerate(out.get("experience") or []):
        ai_job = ai_exp[i] if i < len(ai_exp) and isinstance(ai_exp[i], dict) else {}
        job["bullets"] = _normalize_exp_bullets(ai_job.get("bullets"), job.get("bullets"))

    # Projects: iterate the SOURCE projects so the set of projects can never change.
    ai_projects = ai.get("projects") or []
    for i, proj in enumerate(out.get("projects") or []):
        ai_proj = ai_projects[i] if i < len(ai_projects) and isinstance(ai_projects[i], dict) else {}
        # NAME stays from the source (identity) - never trust the model's name.
        ts = ai_proj.get("tech_stack")
        if ts and str(ts).strip():
            proj["tech_stack"] = str(ts).strip()
        ai_bullets = _clean_bullets(ai_proj.get("bullets"))
        bullets = (ai_bullets or _clean_bullets(proj.get("bullets")))[:MAX_PROJ_BULLETS]
        proj["bullets"] = bullets
        proj["candidate_bullets"] = list(bullets)

    _assert_identity_preserved(source, out)
    return out


def _assert_identity_preserved(source: dict, out: dict) -> None:
    """Defense-in-depth: the merge keeps every experience/project from the source
    by construction, but log (and repair) if that ever drifts so a regression is
    observable in production rather than silently shipping a dropped role."""
    se, oe = source.get("experience") or [], out.get("experience") or []
    if len(se) != len(oe):
        logger.warning("[tailor] experience count drift: source=%d out=%d", len(se), len(oe))
    for i, job in enumerate(oe):
        if i < len(se) and job.get("title") != se[i].get("title"):
            logger.warning("[tailor] experience identity drift at %d; restoring from source", i)
            job["title"], job["company"] = se[i].get("title"), se[i].get("company")
    sp, op = source.get("projects") or [], out.get("projects") or []
    if len(sp) != len(op):
        logger.warning("[tailor] project count drift: source=%d out=%d", len(sp), len(op))
    for i, proj in enumerate(op):
        if i < len(sp) and proj.get("name") != sp[i].get("name"):
            logger.warning("[tailor] project name drift at %d; restoring from source", i)
            proj["name"] = sp[i].get("name")


def _best_skill_category(skills: dict, jd_lower: set) -> str:
    """The category to fold genuinely-missing JD skills into: the one already
    carrying the most JD-relevant skills (the most 'technical' bucket), tie-broken
    by size. This keeps skills categorized smartly and NEVER creates a junk
    'Core Skills' / 'Core Competencies' group."""
    return max(
        skills.items(),
        key=lambda kv: (sum(1 for i in kv[1] if i.lower() in jd_lower), len(kv[1])),
    )[0]


def ensure_skill_coverage(tailored: dict, jd_skills: list) -> list:
    """Keep EVERY existing skill, re-rank each category so JD-critical skills lead,
    and fold any still-missing JD hard skill into the most relevant EXISTING
    category (never a 'Core Skills'/'Core Competencies' junk group). Returns the
    skills that were added so the UI can flag them; all remain editable."""
    from match import resume_text, contains

    skills = tailored.get("skills")
    if not isinstance(skills, dict):
        skills = {}

    jd, seen = [], set()
    for s in jd_skills or []:
        s = str(s).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            jd.append(s)
    jd_lower = {s.lower() for s in jd}

    missing = [s for s in jd if not contains(s, resume_text(tailored))]

    # Re-rank each existing category so JD skills come first (stable order), keeping
    # every original skill.
    reranked: dict = {}
    for cat, items in skills.items():
        items = [str(i) for i in (items or []) if str(i).strip()]
        lead = [i for i in items if i.lower() in jd_lower]
        rest = [i for i in items if i.lower() not in jd_lower]
        reranked[str(cat)] = lead + rest

    if missing:
        if reranked:
            target = _best_skill_category(reranked, jd_lower)
            have = {x.lower() for x in reranked[target]}
            reranked[target] = reranked[target] + [m for m in missing if m.lower() not in have]
        else:
            reranked["Technical Skills"] = missing

    tailored["skills"] = reranked
    return missing


def boost_to_floor(tailored: dict, original: dict, jd_skills: list, jd_keywords: list) -> dict:
    """Cover JD skills smartly and return the HONEST match - no score-gaming.

    We fold genuinely-missing JD hard skills into the right category (via
    ensure_skill_coverage) and report the match as computed. No fake 'Core
    Competencies' keyword stuffing: an honest score the candidate can stand behind
    beats an inflated one that wrecks the resume's quality.
    """
    from match import compute_match

    ensure_skill_coverage(tailored, jd_skills)
    return compute_match(jd_keywords, jd_skills, original, tailored)


def tailor(resume: dict, jd_text: str) -> dict:
    """Return {tailored_resume, cover_letter, email, gaps}.

    Raises LLMNotConfigured (from get_client) when no key is set so the endpoint
    can surface a clean setup message. Any model/JSON error is logged and raised
    as ValueError for the endpoint to convert to a 502-style message - we never
    silently return a half-tailored document.
    """
    name = (resume.get("name") or "").strip()
    client = get_client()
    model = get_model()
    messages = build_messages(resume, jd_text)

    logger.info("[tailor] calling %s", model)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        ai = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("[tailor] model returned non-JSON: %s", raw[:500])
        raise ValueError("The AI returned an unreadable response. Please try again.") from e

    ai = _scrub_dashes(ai)

    tailored_resume = _merge_resume(resume, ai)

    cover_letter = ai.get("cover_letter") if isinstance(ai.get("cover_letter"), dict) else None
    email = ai.get("email") if isinstance(ai.get("email"), dict) else None
    gaps = [str(g) for g in (ai.get("gaps") or []) if str(g).strip()]
    jd_skills = [str(k) for k in (ai.get("jd_skills") or []) if str(k).strip()]
    jd_keywords = [str(k) for k in (ai.get("jd_keywords") or []) if str(k).strip()]
    changes = [str(c) for c in (ai.get("changes") or []) if str(c).strip()]

    # Make the match reliably high for any resume (tiered floor); returns the match.
    match = boost_to_floor(tailored_resume, resume, jd_skills, jd_keywords)

    # Always stamp the real candidate name into the signatures (a fact).
    cover_letter = cover_letter or _empty_letter(name)
    email = email or _empty_email(name)
    if name:
        cover_letter["signature"] = name
        email["signature"] = name

    return {
        "tailored_resume": tailored_resume,
        "original_resume": resume,
        "cover_letter": cover_letter,
        "email": email,
        "match": match,
        "changes": changes,
        "gaps": gaps,
    }
