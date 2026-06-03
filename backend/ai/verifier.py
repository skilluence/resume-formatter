"""Fidelity checker for AI-structured resumes.

The OpenAI structuring step (``ai/structurer.py``) occasionally fabricates
content that was never in the uploaded resume -- invented certifications,
guessed issuers/dates, padded bullets, reconstructed links. The system prompt
forbids this, but a prompt is only a *request*; an LLM is a text generator and
will sometimes ignore it. This module is the enforcement layer: it runs right
after the model and removes any value that cannot be traced back to the
original source text.

Design goal (per the client): "keep it the way it is -- no new word or line",
but *blunder-safe* -- a real line that the model merely reflowed, re-cased or
split out of a comma list must never be dropped. We achieve that by normalizing
both the source and each candidate the same way before comparing, and by using
a generous token-overlap threshold for long free text.

This module is pure standard library -- no network, no OpenAI, no API key.
"""

from __future__ import annotations

import copy
import logging
import re
import unicodedata

logger = logging.getLogger("resume.verifier")

# A long value is "grounded" if at least this fraction of its distinct word
# tokens appear in the source. Lower than 1.0 so a couple of PDF-mangled or
# re-ordered words in a genuine bullet don't cause a false drop; high enough
# that a fabricated sentence (invented claims/metrics) fails.
GROUND_RATIO = 0.80

# Values this short (skills, dates, a company name, a handle) must match
# *every* token -- they're too short to allow partial credit.
SHORT_TOKEN_MAX = 2

# Dashes and bullet glyphs are flattened to spaces on BOTH sides, so the
# leading "- " of a bullet and a hyphen inside "INDEX-MATCH" are treated the
# same in source and candidate (and therefore still match).
_DASHES_BULLETS = "–—−‐‑·•▪◦*-"

# Structural punctuation flattened to spaces. NOTE we deliberately KEEP
# . / @ + # & %  -- they carry meaning in emails, URLs, "Node.js", "C++",
# "C#", "R&D" and metrics like "30%".
_PUNCT_TO_SPACE = ",;:|()[]{}\"'`"

# URL scheme noise stripped so a "mailto:"-cleaned email or a scheme-normalized
# URL still matches the raw form sitting in the source's EMBEDDED LINKS block.
_URL_NOISE = ("mailto:", "tel:", "https://", "http://", "www.")


def _normalize(s) -> str:
    """Lower-case, strip URL/scheme noise, flatten dashes & structural
    punctuation to spaces, and collapse whitespace. Applied identically to the
    source text and to every candidate value."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    for noise in _URL_NOISE:
        s = s.replace(noise, " ")
    s = s.translate({ord(c): " " for c in _DASHES_BULLETS})
    s = s.translate({ord(c): " " for c in _PUNCT_TO_SPACE})
    return re.sub(r"\s+", " ", s).strip()


def _is_grounded(value, norm_source: str, source_tokens: set) -> bool:
    """True if `value`'s text can be traced to the source. Empty values are
    grounded (nothing was fabricated)."""
    nv = _normalize(value)
    if not nv:
        return True
    if nv in norm_source:  # contiguous match -- handles reflow / recase / comma-split
        return True
    tokens = nv.split()
    if len(tokens) <= SHORT_TOKEN_MAX:
        return all(t in source_tokens for t in tokens)
    distinct = set(tokens)
    found = sum(1 for t in distinct if t in source_tokens)
    return (found / len(distinct)) >= GROUND_RATIO


def verify_against_source(structured: dict, raw_text: str) -> dict:
    """Return a new dict containing only content grounded in ``raw_text``.

    - ungrounded scalar fields  -> "" (the formatter skips empty values; "" is
      used instead of None because some fields are interpolated unconditionally
      and None would render the literal text "None")
    - ungrounded list items     -> dropped individually
    - ungrounded entries        -> removed whole (a certification/project whose
      name, or an additional section whose heading, isn't in the source; an
      experience entry only if BOTH title and company are ungrounded)
    - ``name``                  -> never dropped (may come from the filename)

    Does not mutate the input. Every removal is logged.
    """
    if not isinstance(structured, dict):
        return structured

    norm_source = _normalize(raw_text)
    if not norm_source:
        logger.warning(
            "[verifier] source text is empty after normalization -- skipping "
            "verification so nothing real is dropped"
        )
        return structured

    source_tokens = set(norm_source.split())
    data = copy.deepcopy(structured)
    stats = {"entries": 0, "scalars": 0, "items": 0}

    def grounded(value) -> bool:
        return _is_grounded(value, norm_source, source_tokens)

    def null_scalar(container: dict, key: str, label: str):
        """Blank an ungrounded scalar (set to "" so the formatter skips it)."""
        val = container.get(key)
        if val is None or val == "":
            return
        if not grounded(val):
            container[key] = ""
            stats["scalars"] += 1
            logger.info("[verifier] BLANKED %s.%s=%r (not in source)", label, key, val)

    def clean_list(values, label: str) -> list:
        """Drop ungrounded string items, keep the rest (and any non-strings)."""
        if not isinstance(values, list):
            return values
        kept = []
        for item in values:
            if isinstance(item, str) and item.strip() and not grounded(item):
                stats["items"] += 1
                logger.info("[verifier] DROPPED %s item %r", label, item)
                continue
            kept.append(item)
        return kept

    # --- top-level scalars ---------------------------------------------------
    null_scalar(data, "headline", "root")
    null_scalar(data, "summary", "root")

    # --- contact -------------------------------------------------------------
    contact = data.get("contact")
    if isinstance(contact, dict):
        for key in ("phone", "email", "linkedin", "github", "location"):
            null_scalar(contact, key, "contact")
        links = contact.get("links")
        if isinstance(links, list):
            kept_links = []
            for link in links:
                url = link.get("url") if isinstance(link, dict) else None
                if url and not grounded(url):
                    stats["items"] += 1
                    logger.info("[verifier] DROPPED contact.link url=%r", url)
                    continue
                kept_links.append(link)
            contact["links"] = kept_links

    # --- skills (dict of category -> [items]) --------------------------------
    skills = data.get("skills")
    if isinstance(skills, dict):
        cleaned = {}
        for category, items in skills.items():
            kept = clean_list(items, f"skills[{category!r}]")
            if isinstance(kept, list) and not kept:
                # All items in this category were fabricated -> drop the empty key.
                logger.info("[verifier] DROPPED empty skills category %r", category)
                continue
            cleaned[category] = kept
        data["skills"] = cleaned

    # --- experience (drop entry only if BOTH title & company ungrounded) -----
    exp = data.get("experience")
    if isinstance(exp, list):
        kept_jobs = []
        for job in exp:
            if not isinstance(job, dict):
                kept_jobs.append(job)
                continue
            title, company = job.get("title"), job.get("company")
            if title and company and not grounded(title) and not grounded(company):
                stats["entries"] += 1
                logger.info(
                    "[verifier] DROPPED experience entry title=%r company=%r (neither in source)",
                    title, company,
                )
                continue
            for key in ("title", "company", "location", "start_date", "end_date"):
                null_scalar(job, key, "experience")
            job["bullets"] = clean_list(job.get("bullets"), "experience.bullets")
            kept_jobs.append(job)
        data["experience"] = kept_jobs

    # --- projects (drop entry if name ungrounded) ----------------------------
    projects = data.get("projects")
    if isinstance(projects, list):
        kept_projects = []
        for proj in projects:
            if not isinstance(proj, dict):
                kept_projects.append(proj)
                continue
            name = proj.get("name")
            if name and not grounded(name):
                stats["entries"] += 1
                logger.info("[verifier] DROPPED project %r (not in source)", name)
                continue
            null_scalar(proj, "tech_stack", "projects")
            proj["bullets"] = clean_list(proj.get("bullets"), "projects.bullets")
            kept_projects.append(proj)
        data["projects"] = kept_projects

    # --- certifications (drop entry if name ungrounded -- the reported bug) --
    certs = data.get("certifications")
    if isinstance(certs, list):
        kept_certs = []
        for cert in certs:
            if not isinstance(cert, dict):
                kept_certs.append(cert)
                continue
            name = cert.get("name")
            if name and not grounded(name):
                stats["entries"] += 1
                logger.info("[verifier] DROPPED certification %r (not in source)", name)
                continue
            null_scalar(cert, "issuer", "certifications")
            null_scalar(cert, "date", "certifications")
            cert["bullets"] = clean_list(cert.get("bullets"), "certifications.bullets")
            kept_certs.append(cert)
        data["certifications"] = kept_certs

    # --- education (blank ungrounded fields; keep entries) -------------------
    education = data.get("education")
    if isinstance(education, list):
        for edu in education:
            if isinstance(edu, dict):
                for key in ("degree", "institution", "graduation_date"):
                    null_scalar(edu, key, "education")

    # --- additional_sections (drop section if heading ungrounded) ------------
    extras = data.get("additional_sections")
    if isinstance(extras, list):
        kept_extras = []
        for section in extras:
            if not isinstance(section, dict):
                kept_extras.append(section)
                continue
            heading = section.get("heading")
            if heading and not grounded(heading):
                stats["entries"] += 1
                logger.info("[verifier] DROPPED additional section %r (not in source)", heading)
                continue
            section["items"] = clean_list(section.get("items"), "additional_sections.items")
            null_scalar(section, "text", "additional_sections")
            kept_extras.append(section)
        data["additional_sections"] = kept_extras

    # --- name is never dropped, but warn if we couldn't verify it ------------
    name = data.get("name")
    if name and not grounded(name):
        logger.warning("[verifier] KEPT unverified name=%r (may come from filename/header)", name)

    if stats["entries"] or stats["scalars"] or stats["items"]:
        logger.info(
            "[verifier] removed %d fabricated entr%s, blanked %d field(s), dropped %d list item(s)",
            stats["entries"], "y" if stats["entries"] == 1 else "ies",
            stats["scalars"], stats["items"],
        )
    return data
