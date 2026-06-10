"""Deterministic JD <-> resume keyword match scoring (no AI).

Mirrors how real ATS engines score: a WEIGHTED keyword match where hard skills
count more than soft/process keywords. We compute the score for the original resume
and the tailored resume, plus per-list deltas (what was missing before, what is
still missing, and what tailoring ADDED). Transparent and reproducible.

Weights: each hard skill = 2, each other keyword = 1 (matches the 2x hard-skill
emphasis documented across Workday/Taleo/Lever scoring breakdowns).
"""
import re

SKILL_WEIGHT = 2
KEYWORD_WEIGHT = 1


def resume_text(resume: dict) -> str:
    """Flatten the searchable parts of a structured resume into one lowercase blob:
    headline, summary, skills, experience bullets, and projects - the fields a JD
    keyword can realistically land in."""
    parts: list[str] = []
    if not isinstance(resume, dict):
        return ""
    if resume.get("headline"):
        parts.append(str(resume["headline"]))
    if resume.get("summary"):
        parts.append(str(resume["summary"]))
    skills = resume.get("skills") or {}
    if isinstance(skills, dict):
        for cat, items in skills.items():
            parts.append(str(cat))
            parts.extend(str(s) for s in (items or []))
    for job in resume.get("experience") or []:
        parts.append(str(job.get("title", "")))
        parts.extend(str(b) for b in (job.get("bullets") or []))
    for proj in resume.get("projects") or []:
        parts.append(str(proj.get("name", "")))
        if proj.get("tech_stack"):
            parts.append(str(proj["tech_stack"]))
        parts.extend(str(b) for b in (proj.get("bullets") or []))
    # Strip the **bold** markup so it never breaks a word-boundary match.
    return " ".join(parts).replace("*", " ").lower()


def contains(keyword: str, text: str) -> bool:
    """Case-insensitive presence test. Word-boundary for short alphanumeric tokens;
    plain substring for multiword / symbol-bearing terms (e.g. "CI/CD", "Node.js")."""
    kw = (keyword or "").strip().lower()
    if not kw:
        return False
    if re.fullmatch(r"[a-z0-9]+", kw):
        return re.search(rf"\b{re.escape(kw)}\b", text) is not None
    return kw in text


def _dedupe(keywords) -> list:
    seen, out = set(), []
    for k in keywords or []:
        s = str(k).strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _split(keywords: list, text: str):
    """(matched, missing) for one keyword list against one text blob."""
    matched, missing = [], []
    for k in keywords:
        (matched if contains(k, text) else missing).append(k)
    return matched, missing


def _delta(keywords: list, before_text: str, after_text: str) -> dict:
    """For a keyword list: what's missing before, missing after, and newly ADDED
    (present after tailoring but absent before = the change to highlight)."""
    _, missing_before = _split(keywords, before_text)
    matched_after, missing_after = _split(keywords, after_text)
    before_lower = before_text
    added = [k for k in matched_after if not contains(k, before_lower)]
    return {"missing_before": missing_before, "missing_after": missing_after, "added": added}


def compute_match(jd_keywords: list, jd_skills: list, original: dict, tailored: dict) -> dict:
    """Weighted before/after match with per-list deltas.

    A term appearing in BOTH lists is treated as a skill (removed from keywords) so
    it is never double-counted."""
    skills = _dedupe(jd_skills)
    skill_set = {s.lower() for s in skills}
    keywords = [k for k in _dedupe(jd_keywords) if k.lower() not in skill_set]

    before = resume_text(original)
    after = resume_text(tailored)

    skills_delta = _delta(skills, before, after)
    keywords_delta = _delta(keywords, before, after)

    total = SKILL_WEIGHT * len(skills) + KEYWORD_WEIGHT * len(keywords)

    def _score(missing_skills, missing_keywords):
        if not total:
            return 0
        matched_skills = len(skills) - len(missing_skills)
        matched_keywords = len(keywords) - len(missing_keywords)
        got = SKILL_WEIGHT * matched_skills + KEYWORD_WEIGHT * matched_keywords
        return round(got / total * 100)

    return {
        "score_before": _score(skills_delta["missing_before"], keywords_delta["missing_before"]),
        "score_after": _score(skills_delta["missing_after"], keywords_delta["missing_after"]),
        "skills": skills_delta,
        "keywords": keywords_delta,
        "jd_skills": skills,
        "jd_keywords": keywords,
    }
