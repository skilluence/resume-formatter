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


def _merge_resume(source: dict, ai: dict) -> dict:
    """Build the tailored resume: AI provides wording, source provides every fact.

    - headline / summary / skills / projects: taken from the AI (content fields).
    - experience: AI supplies bullets ONLY; title/company/location/dates come from
      the source job at the same index (re-stamped, never trusted from the model).
    - name / contact / education / certifications / additional_sections: verbatim
      from the source. These are facts and are never sent through the model.
    """
    out = copy.deepcopy(source)

    if ai.get("headline"):
        out["headline"] = ai["headline"]
    if ai.get("summary"):
        out["summary"] = ai["summary"]
    if isinstance(ai.get("skills"), dict) and ai["skills"]:
        # Keep only list-of-strings categories; drop anything malformed.
        out["skills"] = {
            str(k): [str(s) for s in v if str(s).strip()]
            for k, v in ai["skills"].items()
            if isinstance(v, list) and any(str(s).strip() for s in v)
        }

    ai_exp = ai.get("experience") or []
    for i, job in enumerate(out.get("experience") or []):
        if i < len(ai_exp) and isinstance(ai_exp[i], dict):
            bullets = ai_exp[i].get("bullets")
            if isinstance(bullets, list) and bullets:
                job["bullets"] = [str(b) for b in bullets if str(b).strip()]

    ai_projects = ai.get("projects")
    if isinstance(ai_projects, list) and ai_projects:
        cleaned = []
        for p in ai_projects:
            if not isinstance(p, dict):
                continue
            cleaned.append(
                {
                    "name": str(p.get("name") or "").strip(),
                    "tech_stack": (str(p.get("tech_stack")).strip() or None)
                    if p.get("tech_stack")
                    else None,
                    "bullets": [str(b) for b in (p.get("bullets") or []) if str(b).strip()],
                }
            )
        if cleaned:
            out["projects"] = cleaned

    return out


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

    # Always stamp the real candidate name into the signatures (a fact).
    cover_letter = cover_letter or _empty_letter(name)
    email = email or _empty_email(name)
    if name:
        cover_letter["signature"] = name
        email["signature"] = name

    return {
        "tailored_resume": tailored_resume,
        "cover_letter": cover_letter,
        "email": email,
        "gaps": gaps,
    }
