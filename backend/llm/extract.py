"""Robust LLM-based resume extraction for the /tailor flow ONLY.

The deterministic `structurer.py` stays the no-AI parser for `/format`. Here, because
`/tailor` is already an AI flow, we let the model read the raw resume text and pull
out structure - it handles arbitrary layouts the rule parser mangles (multiple
certifications on one line, dates on their own line, two-column PDFs). Then we
VALIDATE so the model can neither invent a fact nor lose an entry:

  - grounding  : an entry whose IDENTITY (who/where) isn't in the source is dropped,
  - cross-check: the output never has fewer experiences/projects/certs/education
                 than the deterministic parser found (recover any the model missed),
  - coverage   : any source line not represented is filed under Additional
                 Information (lossless, reusing structurer._recover_dropped).

On any LLM failure we fall back to the deterministic parser, so `/tailor` never breaks.
"""
import logging

from llm.client import get_client, get_model
from llm.prompts import build_extract_messages
from structurer import structure_resume, _norm_tokens, _recover_dropped, _EMBEDDED_MARKER

logger = logging.getLogger("resume.extract")

import json  # noqa: E402  (kept after the local imports for readability)


def _str_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_list(v):
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def _blank_contact():
    return {
        "phone": None, "email": None, "email_label": None,
        "linkedin": None, "linkedin_label": None,
        "github": None, "github_label": None, "location": None, "links": [],
    }


def _normalize(ai: dict) -> dict:
    """Coerce the model's JSON into the EXACT structurer shape (every key present,
    right types), so tailor.py / match.py / compact_ats.py work unchanged."""
    ai = ai if isinstance(ai, dict) else {}

    contact = _blank_contact()
    src = ai.get("contact") if isinstance(ai.get("contact"), dict) else {}
    for k in ("phone", "email", "email_label", "linkedin", "linkedin_label", "github", "github_label", "location"):
        if src.get(k) not in (None, ""):
            contact[k] = _str_or_none(src[k])
    if isinstance(src.get("links"), list):
        contact["links"] = [
            {"label": str(l.get("label") or "").strip(), "url": str(l.get("url") or "").strip()}
            for l in src["links"] if isinstance(l, dict) and (l.get("url") or l.get("label"))
        ]

    def exp(e):
        e = e if isinstance(e, dict) else {}
        return {
            "title": str(e.get("title") or "").strip(),
            "company": str(e.get("company") or "").strip(),
            "location": _str_or_none(e.get("location")),
            "start_date": str(e.get("start_date") or "").strip(),
            "end_date": str(e.get("end_date") or "").strip(),
            "bullets": _clean_list(e.get("bullets")),
        }

    def proj(p):
        p = p if isinstance(p, dict) else {}
        return {"name": str(p.get("name") or "").strip(), "tech_stack": _str_or_none(p.get("tech_stack")),
                "bullets": _clean_list(p.get("bullets"))}

    def edu(e):
        e = e if isinstance(e, dict) else {}
        return {
            "degree": str(e.get("degree") or "").strip(),
            "institution": str(e.get("institution") or "").strip(),
            "location": _str_or_none(e.get("location")),
            "graduation_date": _str_or_none(e.get("graduation_date")),
            "gpa": _str_or_none(e.get("gpa")),
            "details": _clean_list(e.get("details")),
        }

    def cert(c):
        c = c if isinstance(c, dict) else {}
        return {"name": str(c.get("name") or "").strip(), "issuer": _str_or_none(c.get("issuer")),
                "date": _str_or_none(c.get("date")), "bullets": _clean_list(c.get("bullets"))}

    def addl(a):
        a = a if isinstance(a, dict) else {}
        style = str(a.get("style") or "list").strip() or "list"
        return {"heading": str(a.get("heading") or "").strip(), "style": style,
                "items": _clean_list(a.get("items")), "text": _str_or_none(a.get("text"))}

    skills = {}
    if isinstance(ai.get("skills"), dict):
        for k, v in ai["skills"].items():
            items = _clean_list(v)
            if items:
                skills[str(k).strip()] = items

    return {
        "name": str(ai.get("name") or "").strip(),
        "headline": _str_or_none(ai.get("headline")),
        "contact": contact,
        "summary": _str_or_none(ai.get("summary")),
        "skills": skills,
        "experience": [exp(e) for e in (ai.get("experience") or []) if isinstance(e, dict)],
        "projects": [proj(p) for p in (ai.get("projects") or []) if isinstance(p, dict)],
        "education": [edu(e) for e in (ai.get("education") or []) if isinstance(e, dict)],
        "certifications": [cert(c) for c in (ai.get("certifications") or []) if isinstance(c, dict)],
        "additional_sections": [addl(a) for a in (ai.get("additional_sections") or []) if isinstance(a, dict)],
    }


def _grounded(source_tokens: set, *parts, threshold: float = 0.5) -> bool:
    """True if the entry's identity tokens are (mostly) present in the source text."""
    toks = _norm_tokens(" ".join(str(p) for p in parts if p))
    if not toks:
        return True  # nothing to verify - don't drop on an empty identity
    return sum(1 for t in toks if t in source_tokens) / len(toks) >= threshold


def _drop_ungrounded(resume: dict, source_tokens: set):
    """Drop any entry whose identity isn't in the source - the model invented it.
    Bullets/wording are reworded later by tailor(); identity (who/where) is a fact."""
    resume["experience"] = [e for e in resume["experience"] if _grounded(source_tokens, e["title"], e["company"])]
    resume["projects"] = [p for p in resume["projects"] if _grounded(source_tokens, p["name"])]
    resume["certifications"] = [c for c in resume["certifications"] if _grounded(source_tokens, c["name"])]
    resume["education"] = [e for e in resume["education"] if _grounded(source_tokens, e["degree"], e["institution"])]


def _identity_tokens(entry: dict, keys: tuple) -> set:
    return _norm_tokens(" ".join(str(entry.get(k) or "") for k in keys))


def _recover_missing(kept: list, det: list, keys: tuple):
    """Append deterministic entries whose identity matches none of the kept ones,
    so an entry the model omitted is recovered with proper structure."""
    kept_sets = [_identity_tokens(e, keys) for e in kept]
    for d in det:
        dtoks = _identity_tokens(d, keys)
        if not dtoks:
            continue
        if not any(len(dtoks & ks) / len(dtoks) >= 0.5 for ks in kept_sets if ks):
            kept.append(d)
            kept_sets.append(dtoks)


def _cross_check(resume: dict, det: dict):
    """Belt-and-suspenders: never end with fewer entries than the deterministic
    parser found. Recovers anything the model dropped, with real structure."""
    pairs = [("experience", ("title", "company")), ("projects", ("name",)),
             ("certifications", ("name",)), ("education", ("degree", "institution"))]
    for key, idkeys in pairs:
        dets = det.get(key) or []
        if len(resume.get(key) or []) < len(dets):
            _recover_missing(resume[key], dets, idkeys)


def extract_resume(raw_text: str) -> dict:
    """Parse a raw resume into the structured dict, robustly. LLM-led, fact-checked,
    with a deterministic floor and fallback."""
    det = structure_resume(raw_text)
    try:
        client = get_client()
        model = get_model()
        resp = client.chat.completions.create(
            model=model,
            messages=build_extract_messages(raw_text),
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        ai = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        logger.warning("[extract] LLM extraction unavailable (%s); using deterministic parser", e)
        return det

    resume = _normalize(ai)
    if not resume["name"]:
        resume["name"] = det.get("name") or ""
    if not resume["experience"] and not resume["education"]:
        logger.warning("[extract] model returned an empty resume; using deterministic parser")
        return det

    source_tokens = _norm_tokens(raw_text)
    _drop_ungrounded(resume, source_tokens)
    _cross_check(resume, det)
    # Coverage net, but FIRST strip the "EMBEDDED LINKS:" trailer the parsers append
    # (real hyperlink targets used for contact extraction, not resume body content) -
    # otherwise a bare "mailto:..." line gets dumped into Additional Information.
    content_lines = []
    for line in raw_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith(_EMBEDDED_MARKER):
            break
        content_lines.append(s)
    _recover_dropped(resume, content_lines)
    return resume
