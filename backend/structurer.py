"""Rule-based resume structurer (no AI).

Turns the plain text extracted from a resume (``parsers/pdf_parser.py`` or
``parsers/docx_parser.py``) into the structured dict the formatter and the
review UI consume. It replaces the old OpenAI step: because uploads follow
Skilluence's known templates, a handful of deterministic rules read them
reliably — and unlike an LLM, rules can never invent data.

Design rule #1 — **never lose text.** Every non-empty source line must land
somewhere in the output. When a line can't be classified confidently it is
kept verbatim in the closest bucket (a bullet, a detail, or an
"Additional Information" section) rather than dropped. At worst the parser
*mislabels* (e.g. swaps title/company between the two templates) — and the
review screen lets the user fix labels. ``_recover_dropped`` is the final guard.

Two templates are supported in one pass, distinguished per line:
  * PDF style  — job line ``Title | Company  Dates | Location``, ``•`` bullets.
  * Word style — job line ``Company / Title — sub <TAB> Dates | Location``,
    section "Work EXPERIENCE", bullets marked by the DOCX extractor.

Pure standard library — no network, no OpenAI, no API key.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("resume.structurer")

# --- bullets -----------------------------------------------------------------
_BULLET_GLYPHS = ("•", "·", "‣", "◦", "▪", "●", "∙", "")
_BULLET_RE = re.compile(r"^\s*([•·‣◦▪●∙*]|[-–—])\s+")

# --- dates -------------------------------------------------------------------
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DATE_TOKEN = rf"(?:{_MONTH}\s+)?\d{{4}}"
_DATE_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*[–—\-]\s*(?P<end>Present|Current|Ongoing|{_DATE_TOKEN})",
    re.IGNORECASE,
)

# --- contact bits ------------------------------------------------------------
_EMAIL_RE = re.compile(r"[^\s|]+@[^\s|]+\.[^\s|]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,}\d")
_GPA_RE = re.compile(r"\b(?:c?gpa|grade)\b|\b\d(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\b|\b\d{1,3}(?:\.\d+)?\s*%", re.IGNORECASE)

# --- section headings (known synonyms -> canonical type) ---------------------
_SECTION_SYNONYMS = {
    "summary": [
        "professional summary", "summary", "profile", "professional profile",
        "objective", "career objective", "about", "about me", "executive summary",
        "career summary", "professional overview", "overview",
    ],
    "skills": [
        "technical skills", "skills", "core competencies", "competencies",
        "technical proficiencies", "areas of expertise", "technologies", "tools",
        "technical expertise", "key skills", "skills & expertise", "core skills",
        "technical skills & tools",
    ],
    "experience": [
        "professional experience", "work experience", "experience", "employment",
        "work history", "employment history", "professional background",
        "relevant experience", "career experience",
    ],
    "projects": [
        "projects", "personal projects", "key projects", "academic projects",
        "selected projects", "project experience", "notable projects",
    ],
    "education": [
        "education", "academic background", "qualifications", "academic qualifications",
        "educational background", "education & training",
    ],
    "certifications": [
        "certifications", "certification", "licenses", "licenses & certifications",
        "licenses and certifications", "courses", "certifications & licenses",
        "certifications and licenses",
    ],
}
# Flatten to phrase -> type for O(1) exact lookup.
_HEADING_LOOKUP = {phrase: typ for typ, phrases in _SECTION_SYNONYMS.items() for phrase in phrases}

_EMBEDDED_MARKER = "embedded links:"


# ─────────────────────────── small helpers ──────────────────────────────────

def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line, count=1).strip()


def _starts_lower(line: str) -> bool:
    """A wrapped continuation line (from a PDF) usually breaks mid-sentence, so
    it starts with a lowercase letter — unlike a heading or a title."""
    s = line.lstrip()
    return bool(s) and s[0].islower()


def _heading_type(line: str):
    """Return the canonical section type for a known heading line, else None."""
    norm = re.sub(r"\s+", " ", line.strip().rstrip(":").lower())
    return _HEADING_LOOKUP.get(norm)


def _looks_like_heading(line: str) -> bool:
    """Generic (unknown) section heading — e.g. ACHIEVEMENTS, AWARDS, LANGUAGES.
    Conservative on purpose: ALL-CAPS, short, no comma/pipe/date/'@'/end-period,
    so skill continuation lines and sentences are never mistaken for headings."""
    s = line.strip()
    if not s or _is_bullet(s):
        return False
    if "|" in s or "@" in s or "," in s or s.endswith((".", ":")):
        return False
    if _DATE_RANGE_RE.search(s):
        return False
    words = s.split()
    if not (1 <= len(words) <= 5):
        return False
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and s.upper() == s  # ALL CAPS


def _split_pipes(line: str) -> list:
    return [seg.strip() for seg in line.split("|") if seg.strip()]


def _extract_date_range(text: str):
    """Return (start, end, text_without_dates) — text keeps everything else."""
    m = _DATE_RANGE_RE.search(text)
    if not m:
        return None, None, text
    start = m.group("start").strip()
    end = m.group("end").strip()
    cleaned = (text[: m.start()] + " " + text[m.end():]).strip(" \t|–—-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return start, end, cleaned


# ─────────────────────────── section parsers ────────────────────────────────

def _parse_contact(contact_line: str, embedded: list) -> dict:
    contact = {"phone": None, "email": None, "linkedin": None, "github": None, "location": None, "links": []}

    for seg in _split_pipes(contact_line):
        low = seg.lower()
        if _EMAIL_RE.search(seg):
            contact["email"] = _EMAIL_RE.search(seg).group(0)
        elif _PHONE_RE.search(seg) and sum(c.isdigit() for c in seg) >= 7:
            contact["phone"] = seg
        elif "linkedin" in low:
            contact["linkedin"] = contact["linkedin"] or seg
        elif "github" in low:
            contact["github"] = contact["github"] or seg
        elif contact["location"] is None:
            contact["location"] = seg
        else:
            contact["links"].append({"label": seg, "url": seg})

    # Embedded URLs are authoritative — they carry the real targets that the
    # visible text ("LinkedIn") only hinted at.
    for url in embedded:
        low = url.lower()
        if low.startswith("mailto:"):
            contact["email"] = url[len("mailto:"):]
        elif "linkedin.com" in low:
            contact["linkedin"] = url
        elif "github.com" in low:
            contact["github"] = url
        elif low.startswith(("http://", "https://", "www.")):
            domain = re.sub(r"^https?://(www\.)?", "", low).split("/")[0]
            contact["links"].append({"label": domain or url, "url": url})
    # If linkedin/github were only the bare word with no real URL, drop them —
    # a label with no target carries no resume data.
    for k in ("linkedin", "github"):
        v = contact[k]
        if v and "." not in v and "/" not in v:
            contact[k] = None
    return contact


def _parse_skills(body: list) -> dict:
    """Lines look like 'Category: a, b, c'. A line with no leading 'Label:' is a
    wrapped continuation and its items append to the current category."""
    skills: dict = {}
    current = None
    for line in body:
        line = _strip_bullet(line) if _is_bullet(line) else line
        m = re.match(r"^([A-Z][A-Za-z0-9 &/+.\-]{0,45}?):\s*(.+)$", line)
        if m:
            current = m.group(1).strip()
            skills.setdefault(current, [])
            items = m.group(2)
        else:
            items = line
        target = current if current is not None else "Skills"
        skills.setdefault(target, [])
        for item in items.split(","):
            item = item.strip()
            if item:
                skills[target].append(item)
    return skills


def _iter_entries(body: list, is_header):
    """Group a section body into (header_line, bullet_lines) entries.

    A line is a header when ``is_header(line)`` is true. Bullets and wrapped
    continuations (a non-bullet line that starts lowercase) attach to the
    current entry so nothing is split apart or lost."""
    entries = []
    cur_header, cur_bullets = None, []
    for line in body:
        if _is_bullet(line):
            cur_bullets.append(_strip_bullet(line))
        elif is_header(line) and not _starts_lower(line):
            if cur_header is not None or cur_bullets:
                entries.append((cur_header, cur_bullets))
            cur_header, cur_bullets = line, []
        else:
            # continuation of the last bullet, or a stray line under the header
            if cur_bullets:
                cur_bullets[-1] = (cur_bullets[-1] + " " + line).strip()
            elif cur_header is not None:
                cur_header = (cur_header + " " + line).strip()
            else:
                cur_header, cur_bullets = line, []
    if cur_header is not None or cur_bullets:
        entries.append((cur_header, cur_bullets))
    return entries


def _parse_job_header(line: str) -> dict:
    """Parse one experience header across both templates (tab => Word style,
    pipes => PDF style)."""
    job = {"title": "", "company": "", "location": None, "start_date": "", "end_date": ""}

    if "\t" in line:  # Word style: "Company / Title — sub \t Dates | Location"
        left, _, right = line.partition("\t")
        start, end, right = _extract_date_range(right)
        job["start_date"], job["end_date"] = start or "", end or ""
        loc = right.lstrip("|").strip()
        job["location"] = loc or None
        if " / " in left:
            company, _, title = left.partition(" / ")
            job["company"], job["title"] = company.strip(), title.strip()
        else:
            job["title"] = left.strip()
        return job

    if "|" in line:  # PDF style: "Title | Company Dates | Location"
        segs = _split_pipes(line)
        date_idx = next((i for i, s in enumerate(segs) if _DATE_RANGE_RE.search(s)), None)
        if date_idx is not None:
            start, end, company = _extract_date_range(segs[date_idx])
            job["start_date"], job["end_date"] = start or "", end or ""
            job["company"] = company
            before = segs[:date_idx]
            after = segs[date_idx + 1:]
            if before:
                job["title"] = before[0]
                if len(before) > 1 and not job["company"]:
                    job["company"] = before[1]
            if after:
                job["location"] = after[-1]
        else:
            job["title"] = segs[0] if segs else line
            if len(segs) > 1:
                job["company"] = segs[1]
            if len(segs) > 2:
                job["location"] = segs[-1]
        return job

    # No tab, no pipe: keep whatever's there as the title (lossless).
    start, end, rest = _extract_date_range(line)
    job["start_date"], job["end_date"] = start or "", end or ""
    job["title"] = rest
    return job


def _parse_experience(body: list) -> list:
    jobs = []
    for header, bullets in _iter_entries(body, lambda l: bool(_DATE_RANGE_RE.search(l))):
        if header is None:
            # bullets with no header — graft onto the previous job, else make a stub
            if jobs:
                jobs[-1]["bullets"].extend(bullets)
                continue
            header = ""
        job = _parse_job_header(header)
        job["bullets"] = bullets
        jobs.append(job)
    return jobs


def _parse_projects(body: list) -> list:
    """Two shapes: PDF 'Name | tech_stack' on one line; Word 'Name' then a
    separate tech-stack line. A lowercase continuation joins the last bullet."""
    projects = []
    cur = None
    for line in body:
        if _is_bullet(line):
            if cur is None:
                cur = {"name": "", "tech_stack": None, "bullets": []}
                projects.append(cur)
            cur["bullets"].append(_strip_bullet(line))
            continue
        if _starts_lower(line) and cur is not None and cur["bullets"]:
            cur["bullets"][-1] = (cur["bullets"][-1] + " " + line).strip()
            continue
        if "|" in line and not _DATE_RANGE_RE.search(line):
            name, _, tech = line.partition("|")
            cur = {"name": name.strip(), "tech_stack": tech.strip() or None, "bullets": []}
            projects.append(cur)
        elif cur is not None and not cur["bullets"] and cur["tech_stack"] is None:
            cur["tech_stack"] = line.strip()  # Word style separate tech line
        else:
            cur = {"name": line.strip(), "tech_stack": None, "bullets": []}
            projects.append(cur)
    return projects


def _parse_education(body: list) -> list:
    entries = []
    cur = None
    for line in body:
        raw = _strip_bullet(line) if _is_bullet(line) else line
        if _DATE_RANGE_RE.search(raw) and not _starts_lower(raw):
            start, end, degree = _extract_date_range(raw)
            grad = end if not start else (f"{start} – {end}" if end else start)
            cur = {"degree": degree, "institution": "", "location": None,
                   "graduation_date": grad, "gpa": None, "details": []}
            entries.append(cur)
        elif cur is None:
            cur = {"degree": raw, "institution": "", "location": None,
                   "graduation_date": None, "gpa": None, "details": []}
            entries.append(cur)
        elif _starts_lower(raw):
            # wrapped continuation of the previous line
            if cur["details"]:
                cur["details"][-1] = (cur["details"][-1] + " " + raw).strip()
            elif cur["institution"]:
                cur["institution"] = (cur["institution"] + " " + raw).strip()
            else:
                cur["degree"] = (cur["degree"] + " " + raw).strip()
        elif not cur["institution"]:
            cur["institution"] = _absorb_education_line(cur, raw)
        else:
            _absorb_detail(cur, raw)
    return entries


def _absorb_education_line(entry: dict, line: str) -> str:
    """The institution line. Pull GPA and location out of it when present
    ('Institution | GPA | Location' or 'Institution, City, ST'). Returns the
    cleaned institution string."""
    if "|" in line:
        segs = _split_pipes(line)
        institution_parts = []
        for seg in segs:
            if entry["gpa"] is None and _GPA_RE.search(seg):
                entry["gpa"] = seg
            elif entry["location"] is None and re.search(r",\s*[A-Za-z .]+$", seg) and seg is not segs[0]:
                entry["location"] = seg
            else:
                institution_parts.append(seg)
        return institution_parts[0] if institution_parts else (segs[0] if segs else "")
    # No pipes (Word style). Try to peel a trailing 'City, ST' as location.
    m = re.search(r",\s*([A-Za-z .]+,\s*[A-Z]{2}|[A-Za-z .]+,\s*[A-Za-z ]+)$", line)
    if m:
        entry["location"] = m.group(1).strip()
        return line[: m.start()].strip()
    return line


def _absorb_detail(entry: dict, line: str):
    """An extra education line: Coursework / Honors / a standalone GPA."""
    if entry["gpa"] is None and re.match(r"^\s*(c?gpa|grade)\b", line, re.IGNORECASE):
        entry["gpa"] = line.strip()
        return
    entry["details"].append(line.strip())


def _parse_certifications(body: list) -> list:
    certs = []
    for line in body:
        if _is_bullet(line):
            raw = _strip_bullet(line)
        elif _starts_lower(line) and certs:
            certs[-1]["bullets"].append(line.strip())
            continue
        else:
            raw = line
        segs = _split_pipes(raw) if "|" in raw else [raw]
        cert = {"name": segs[0], "issuer": None, "date": None, "bullets": []}
        for seg in segs[1:]:
            if _DATE_RANGE_RE.search(seg) or re.search(r"\b\d{4}\b", seg):
                cert["date"] = seg
            elif cert["issuer"] is None:
                cert["issuer"] = seg
            else:
                cert["bullets"].append(seg)
        certs.append(cert)
    return certs


def _parse_additional(heading: str, body: list) -> dict:
    """Any unrecognised section (Achievements, Awards, Languages, ...)."""
    items, prose = [], []
    for line in body:
        if _is_bullet(line):
            items.append(_strip_bullet(line))
        elif _starts_lower(line) and items:
            items[-1] = (items[-1] + " " + line).strip()
        elif _starts_lower(line) and prose:
            prose[-1] = (prose[-1] + " " + line).strip()
        elif items:
            items.append(line.strip())
        else:
            prose.append(line.strip())
    if items:
        return {"heading": heading, "style": "list", "items": items, "text": None}
    return {"heading": heading, "style": "prose", "items": [], "text": " ".join(prose) or None}


# ─────────────────────────── completeness guard ─────────────────────────────

def _norm_tokens(s: str) -> set:
    return set(re.sub(r"[^a-z0-9@./+#]+", " ", (s or "").lower()).split())


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _all_strings(v)


def _recover_dropped(data: dict, content_lines: list) -> dict:
    """Final guard: if any source line isn't represented in the output, file it
    under 'Additional Information' so a parsing miss can never silently lose
    data. Lossless by construction — at worst it surfaces a mislabeled line."""
    captured = set()
    for s in _all_strings(data):
        captured |= _norm_tokens(s)

    missing = []
    for line in content_lines:
        if _looks_like_heading(line) or _heading_type(line):
            continue  # section headers aren't data
        toks = _norm_tokens(_strip_bullet(line) if _is_bullet(line) else line)
        if not toks:
            continue
        found = sum(1 for t in toks if t in captured)
        if found / len(toks) < 0.8:
            missing.append(line.strip())

    if missing:
        logger.info("[structurer] recovered %d unclassified line(s) into Additional Information", len(missing))
        block = next((s for s in data["additional_sections"]
                      if s.get("heading", "").lower() == "additional information"), None)
        if block is None:
            block = {"heading": "Additional Information", "style": "list", "items": [], "text": None}
            data["additional_sections"].append(block)
        block["items"].extend(missing)
    return data


# ─────────────────────────────── entry point ────────────────────────────────

def structure_resume(raw_text: str) -> dict:
    """Parse extracted resume text into the structured schema. Deterministic,
    lossless, AI-free."""
    data = {
        "name": "", "headline": None,
        "contact": {"phone": None, "email": None, "linkedin": None, "github": None, "location": None, "links": []},
        "summary": None, "skills": {}, "experience": [], "projects": [],
        "education": [], "certifications": [], "additional_sections": [],
    }

    # 1. Split off the EMBEDDED LINKS trailer the parsers append.
    embedded = []
    lines = []
    in_links = False
    for raw in (raw_text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.strip().lower().startswith(_EMBEDDED_MARKER):
            in_links = True
            continue
        (embedded if in_links else lines).append(line.strip())
    if not lines:
        return data

    content_lines = list(lines)  # for the completeness guard

    # 2. Header block: name, then headline + contact, up to the first section.
    data["name"] = lines[0]
    idx = 1
    preamble = []
    while idx < len(lines) and _heading_type(lines[idx]) is None and not _looks_like_heading(lines[idx]):
        preamble.append(lines[idx])
        idx += 1
    contact_line = None
    headline_parts = []
    for p in preamble:
        if _EMAIL_RE.search(p) or (_PHONE_RE.search(p) and sum(c.isdigit() for c in p) >= 7) \
                or "linkedin" in p.lower() or "github" in p.lower():
            contact_line = p if contact_line is None else contact_line
            if contact_line is p:
                continue
        headline_parts.append(p)
    if headline_parts:
        data["headline"] = " ".join(headline_parts)
    data["contact"] = _parse_contact(contact_line or "", embedded)

    # 3. Walk the remaining lines section by section.
    sections = []  # (type_or_heading, is_known, body[])
    cur_type, cur_known, cur_body = None, False, []
    while idx < len(lines):
        line = lines[idx]
        known = _heading_type(line)
        if known is not None:
            if cur_type is not None or cur_body:
                sections.append((cur_type, cur_known, cur_body))
            cur_type, cur_known, cur_body = known, True, []
        elif _looks_like_heading(line):
            if cur_type is not None or cur_body:
                sections.append((cur_type, cur_known, cur_body))
            cur_type, cur_known, cur_body = line, False, []
        else:
            cur_body.append(line)
        idx += 1
    if cur_type is not None or cur_body:
        sections.append((cur_type, cur_known, cur_body))

    # 4. Dispatch each section to its parser.
    for typ, known, body in sections:
        if not body:
            continue
        if known and typ == "summary":
            joined = " ".join(body)
            data["summary"] = (data["summary"] + " " + joined).strip() if data["summary"] else joined
        elif known and typ == "skills":
            for k, v in _parse_skills(body).items():
                data["skills"].setdefault(k, []).extend(v)
        elif known and typ == "experience":
            data["experience"].extend(_parse_experience(body))
        elif known and typ == "projects":
            data["projects"].extend(_parse_projects(body))
        elif known and typ == "education":
            data["education"].extend(_parse_education(body))
        elif known and typ == "certifications":
            data["certifications"].extend(_parse_certifications(body))
        else:
            heading = typ if isinstance(typ, str) else "Additional Information"
            data["additional_sections"].append(_parse_additional(heading, body))

    # 5. Final completeness guard.
    return _recover_dropped(data, content_lines)
