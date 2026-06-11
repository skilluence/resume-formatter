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
# Includes the Private-Use-Area range (U+E000–U+F8FF) — Word/PDF exports of
# Symbol/Wingdings bullets land there (e.g. U+F0B7 "•", U+F0A7 "▪"). Those carry
# no text meaning, so a leading one is always a bullet marker.
_BULLET_RE = re.compile(r"^\s*([•·‣◦▪●∙○■◆➢➤»*]|[-]|[–—-])\s+")

# --- dates -------------------------------------------------------------------
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
# `\s*` (not `\s+`) so a missing-space OCR date like "Jan2021" still parses as
# month+year instead of stranding "Jan" on the company name.
_DATE_TOKEN = rf"(?:{_MONTH}\s*)?\d{{4}}"
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
        "projects", "project", "personal projects", "key projects", "academic projects",
        "selected projects", "project experience", "notable projects",
    ],
    "education": [
        "education", "academic background", "qualifications", "academic qualifications",
        "educational background", "education & training",
    ],
    "certifications": [
        "certifications", "certification", "certificate", "certificates", "licenses",
        "licenses & certifications", "licenses and certifications", "courses",
        "certifications & licenses", "certifications and licenses",
    ],
}
# Flatten to phrase -> type for O(1) exact lookup.
_HEADING_LOOKUP = {phrase: typ for typ, phrases in _SECTION_SYNONYMS.items() for phrase in phrases}

# Fallback for ALL-CAPS headings not in the synonym list (e.g. "PROJECT
# MANAGEMENT SKILLS", "WORK EXPERIENCE"). Order matters: a heading containing
# "skill" is a skills section even if it also says "project". Only consulted for
# lines that already look like a heading (ALL CAPS, short) so job titles such as
# "Project Manager" can never trip it.
_HEADING_KEYWORDS = [
    (re.compile(r"skill|competenc|proficienc|expertise|technolog|toolset", re.I), "skills"),
    (re.compile(r"experience|employment|work history", re.I), "experience"),
    (re.compile(r"education|academic|qualification", re.I), "education"),
    (re.compile(r"project", re.I), "projects"),
    (re.compile(r"certificat|licen[sc]e|courses", re.I), "certifications"),
    (re.compile(r"summary|profile|objective|about|overview", re.I), "summary"),
]

_EMBEDDED_MARKER = "embedded links:"


# ─────────────────────────── small helpers ──────────────────────────────────

def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line, count=1).strip()


# Stray control / zero-width / private-use / replacement glyphs (the boxes a PDF
# can leave at line ends) carry no text and only look broken; we drop them.
_BULLET_ORDS = set(range(0xe000, 0xf900)) | {
    0x2022, 0x00b7, 0x2023, 0x25e6, 0x25aa, 0x25cf, 0x2219, 0x25cb, 0x25a0, 0x25c6,
    0x27a2, 0x27a4, 0x00bb, 0x2043, 0x2024, 0x2027, 0x2d, 0x2a,
}


def _sanitize(s: str) -> str:
    def keep(c):
        o = ord(c)
        return not (
            (o < 32 and c != chr(9))
            or 127 <= o <= 159
            or 0x200b <= o <= 0x200f
            or o in (0x2028, 0x2029, 0x2060, 0xfeff)
            or 0xe000 <= o <= 0xf8ff
            or 0xfff9 <= o <= 0xffff
        )
    return "".join(c for c in s if keep(c))


def _is_lone_bullet(s: str) -> bool:
    """A line that is only a bullet glyph (the marker extracted onto its own line,
    with the real text on the following line)."""
    s = s.strip()
    return bool(s) and not re.search(r"[0-9A-Za-z]", s) and any(ord(c) in _BULLET_ORDS for c in s)


def _starts_lower(line: str) -> bool:
    """A wrapped continuation line (from a PDF) usually breaks mid-sentence, so
    it starts with a lowercase letter — unlike a heading or a title."""
    s = line.lstrip()
    return bool(s) and (s[0].islower() or s[0].isdigit())


def _heading_type(line: str):
    """Return the canonical section type for a heading line, else None.

    Tries the exact synonym list first, then an ALL-CAPS keyword fallback so a
    bespoke heading like "PROJECT MANAGEMENT SKILLS" still routes to skills. The
    fallback is gated on ``_looks_like_heading`` so a job title such as
    "Project Manager" (Title Case) can never be mistaken for a section."""
    norm = re.sub(r"\s+", " ", line.strip().rstrip(":").lower())
    if norm in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[norm]
    if _looks_like_heading(line):
        for rx, typ in _HEADING_KEYWORDS:
            if rx.search(norm):
                return typ
    return None


def _looks_like_heading(line: str) -> bool:
    """Generic (unknown) section heading — e.g. ACHIEVEMENTS, AWARDS, LANGUAGES.
    Conservative on purpose: ALL-CAPS, short, no comma/pipe/date/'@'/end-period,
    so skill continuation lines and sentences are never mistaken for headings."""
    s = line.strip()
    if not s or _is_bullet(s):
        return False
    if "|" in s or "@" in s or "," in s or s.endswith((".", ":")):
        return False
    # A real section heading is a label, never a line of data. Three tells of
    # education CONTENT that must NOT be read as a heading (doing so splits the
    # section and scatters the rows):
    #   * digits   — a GPA / percentage / year ("CGPA: 8.5/10", "Class XII 2020")
    #   * an institution or degree keyword ("UNIVERSITY OF NORTH TEXAS")
    #   * an "of" connector in a proper name ("VELLORE INSTITUTE OF TECHNOLOGY")
    # Known headings ("EDUCATION", "AREAS OF EXPERTISE") are matched by the exact
    # synonym list in _heading_type BEFORE this fallback, so excluding them here is
    # safe — the worst case for a bespoke "X OF Y" heading is that its line stays
    # as body text, never lost.
    if any(c.isdigit() for c in s):
        return False
    if _INSTITUTION_RE.search(s) or _DEGREE_RE.search(s) or re.search(r"\bof\b", s, re.I):
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

def _line_has_contact(line: str) -> bool:
    """True if a line carries contact info (email, phone, or a linkedin/github
    mention). Used to locate where the header zone ends and to keep an ALL-CAPS
    job title that sits *above* the contact line inside the header."""
    low = line.lower()
    return bool(
        _EMAIL_RE.search(line)
        or (_PHONE_RE.search(line) and sum(c.isdigit() for c in line) >= 7)
        or "linkedin" in low
        or "github" in low
    )


def _is_urlish(s: str) -> bool:
    """True when a segment looks like an actual URL/handle (has a scheme, www,
    a domain, or a path) rather than just the platform word like 'LinkedIn'."""
    return bool(re.search(r"https?://|www\.|[\w-]+\.(?:com|io|me|dev|net|org|co)\b|/", s.lower()))


def _parse_contact(contact_line: str, embedded: list) -> dict:
    contact = {"phone": None, "email": None, "email_label": None,
               "linkedin": None, "linkedin_label": None,
               "github": None, "github_label": None,
               "location": None, "links": []}

    for seg in _split_pipes(contact_line):
        low = seg.lower()
        if _EMAIL_RE.search(seg):
            contact["email"] = _EMAIL_RE.search(seg).group(0)
        elif _PHONE_RE.search(seg) and sum(c.isdigit() for c in seg) >= 7:
            contact["phone"] = seg
        elif "linkedin" in low:
            # A real URL goes to the link field; the bare word 'LinkedIn' is just
            # the display label (so we never build a bogus linkedin.com/in/LinkedIn).
            if _is_urlish(seg):
                contact["linkedin"] = contact["linkedin"] or seg
            else:
                contact["linkedin_label"] = contact["linkedin_label"] or seg
        elif "github" in low:
            if _is_urlish(seg):
                contact["github"] = contact["github"] or seg
            else:
                contact["github_label"] = contact["github_label"] or seg
        elif contact["location"] is None:
            contact["location"] = seg
        else:
            contact["links"].append({"label": seg, "url": seg})

    # Embedded URLs are authoritative — they carry the real targets that the
    # visible text ("LinkedIn") only hinted at.
    for url in embedded:
        low = url.lower()
        if low.startswith("mailto:"):
            # Prefer the visible email text; only fall back to an embedded mailto
            # when none was written in the contact line. Embedded mailto targets
            # are sometimes placeholders/redactions (e.g. "xx.212@…") that differ
            # from the real, visible address.
            if not contact["email"]:
                contact["email"] = url[len("mailto:"):]
        elif "linkedin.com" in low:
            contact["linkedin"] = url
        elif "github.com" in low:
            contact["github"] = url
        elif low.startswith(("http://", "https://", "www.")):
            domain = re.sub(r"^https?://(www\.)?", "", low).split("/")[0]
            contact["links"].append({"label": domain or url, "url": url})
    # Keep a bare "LinkedIn"/"GitHub" label even with no recovered URL — the
    # person listed it, so we never drop it; the review screen lets them add the
    # link. (When a real URL was embedded, the loop above already replaced it.)
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
    """Group a section body into entries: ``{"header": [lines], "bullets": [..]}``.

    Bullet detection is glyph-independent. If the section uses bullet glyphs,
    only glyph lines start bullets. If it doesn't (some PDFs drop the glyph),
    a capitalised line starts a new bullet and a lowercase line is a wrapped
    continuation. A non-glyph capitalised line *before any bullet* is kept as a
    second header line — e.g. a job title that sits on its own line. Nothing is
    split apart or lost."""
    has_glyphs = any(_is_bullet(l) for l in body)
    entries = []
    cur = None
    for line in body:
        bullet = _is_bullet(line)
        # A glyph bullet is ALWAYS a bullet — never a header — even when it
        # contains an inline date range (e.g. "• …(– phase). | 2020 – 2021").
        if not bullet and is_header(line) and not _starts_lower(line):
            cur = {"header": [line], "bullets": []}
            entries.append(cur)
        elif bullet:
            if cur is None:
                cur = {"header": [], "bullets": []}
                entries.append(cur)
            cur["bullets"].append(_strip_bullet(line))
        elif cur is None:
            cur = {"header": [line], "bullets": []}
            entries.append(cur)
        elif _starts_lower(line):
            if cur["bullets"]:
                cur["bullets"][-1] = (cur["bullets"][-1] + " " + line).strip()
            elif cur["header"]:
                cur["header"][-1] = (cur["header"][-1] + " " + line).strip()
            else:
                cur["header"].append(line)
        elif not has_glyphs:
            cur["bullets"].append(line)            # no-glyph section: a new bullet
        elif not cur["bullets"] and len(line.split()) <= 6:
            cur["header"].append(line)             # a SHORT line alone = a title
        else:
            cur["bullets"].append(line)            # a (glyph-less) bullet sentence
    return entries


_COUNTRIES = {
    "usa", "us", "india", "ind", "uk", "uae", "canada", "germany", "australia",
    "singapore", "sg", "ireland", "netherlands", "france", "spain", "remote",
}


def _looks_like_location(s: str) -> bool:
    """True for a place segment ("San Jose, CA", "Ahmedabad, India", "USA",
    "Remote") — conservative, so a company name with a comma ("Acme, Inc.")
    isn't mistaken for a location."""
    s = s.strip()
    if not s:
        return False
    # A long institution name that merely ends in a city ("New Jersey Institute of
    # Technology – Newark, NJ") is the SCHOOL, not a bare location — don't peel it
    # into the location field and lose it from the institution. The 5-word floor
    # keeps a genuine city that happens to contain a school word ("College Park,
    # MD") working as a location.
    if _INSTITUTION_RE.search(s) and len(s.split()) >= 5:
        return False
    if re.search(r",\s*[A-Z]{2}$", s):                  # "City, ST"
        return True
    last = s.split(",")[-1].strip().lower().strip(".")
    if last in _COUNTRIES:                               # "City, India" / "USA"
        return True
    if "remote" in s.lower() and len(s.split()) <= 3:    # "Remote", "Remote Ready"
        return True
    return False


def _parse_single_job_line(line: str) -> dict:
    """Parse one experience-header line across every layout — pipes, tabs,
    slashes, dashes — pulling the location out wherever it sits. General, not
    tuned to any one template."""
    job = {"title": "", "company": "", "location": None, "start_date": "", "end_date": ""}

    start, end, line = _extract_date_range(line)
    job["start_date"], job["end_date"] = start or "", end or ""

    # Tabs and pipes are the strong field separators.
    segs = [s.strip() for s in re.split(r"[\t|]", line) if s.strip()]

    # Lift out a location segment so it can't pollute title/company.
    loc_idx = next((i for i, s in enumerate(segs) if _looks_like_location(s)), None)
    if loc_idx is not None and len(segs) > 1:
        job["location"] = segs.pop(loc_idx)

    if len(segs) >= 2:
        job["title"], job["company"] = segs[0], segs[1]
        if len(segs) > 2 and not job["location"]:
            job["location"] = segs[-1]
    elif len(segs) == 1:
        seg = segs[0]
        if " / " in seg:                                 # "Company / Title" (slash => company first)
            company, _, title = seg.partition(" / ")
            job["company"], job["title"] = company.strip(), title.strip()
        else:
            dash = [p.strip() for p in re.split(r"\s+[–—]\s+", seg) if p.strip()]
            if len(dash) >= 2:                           # "Title – Company [– Location]"
                job["title"] = dash[0]
                if not job["location"] and len(dash) > 2 and _looks_like_location(dash[-1]):
                    job["location"] = dash[-1]
                    job["company"] = " ".join(dash[1:-1]).strip()
                else:
                    job["company"] = " ".join(dash[1:]).strip()
            else:
                # Lone label: the title is usually on its own line (attached by
                # _parse_job_header), so treat this as the company.
                job["company"] = seg
    return job


def _parse_job_header(header_lines: list) -> dict:
    """Parse a (possibly multi-line) experience header. The line carrying the
    dates is the anchor; any other header line is the title or company that the
    template placed on its own line (e.g. "Company <tab> Dates" then "Title")."""
    if not header_lines:
        return _parse_single_job_line("")
    date_line = next((l for l in header_lines if _DATE_RANGE_RE.search(l)), header_lines[0])
    job = _parse_single_job_line(date_line)
    extra = " ".join(l.strip() for l in header_lines if l != date_line and l.strip()).strip()
    if extra:
        if not job["title"]:
            job["title"] = extra
        elif not job["company"]:
            job["company"] = extra
        else:
            job["title"] = (job["title"] + " " + extra).strip()
    return job


def _is_job_header(line: str) -> bool:
    """A job header carries a date range AND is short once the date is removed
    (a title/company/location line, ~a dozen words). A full-sentence bullet that
    merely mentions a year range is long, so it is NOT treated as a header. This
    is a general rule for every resume, not a per-file patch."""
    if not _DATE_RANGE_RE.search(line):
        return False
    _, _, rest = _extract_date_range(line)
    return len(rest.split()) <= 16


def _merge_title_date_lines(body: list) -> list:
    """Word layouts often put the job TITLE on its own line and the COMPANY+DATES
    on the next line. With no date of its own, the title line never opens a new
    entry, so a later role collapses into the previous job's bullets ("kept 1 of
    2"). Join such a pair with a tab so the dated line anchors one header that
    _is_job_header recognises, and _parse_single_job_line splits title/company on
    the tab. Only fires on a short, capitalised, date-less line IMMEDIATELY above a
    dated header line - the common-case inline header has no such dangling line, so
    its output is unchanged."""
    out, i, n = [], 0, len(body)
    while i < n:
        line, nxt = body[i], (body[i + 1] if i + 1 < n else None)
        if (
            nxt is not None
            and not _is_bullet(line)
            and not _starts_lower(line)
            and not _DATE_RANGE_RE.search(line)
            and len(line.split()) <= 8
            and not _is_bullet(nxt)
            and _is_job_header(nxt)
        ):
            # Join with a pipe (a strong field separator) rather than a tab: a tab
            # adjacent to the removed date is collapsed by _extract_date_range, but
            # a pipe survives, so title/company split cleanly.
            out.append(line.rstrip() + " | " + nxt.strip())
            i += 2
        else:
            out.append(line)
            i += 1
    return out


def _parse_experience(body: list) -> list:
    jobs = []
    for entry in _iter_entries(_merge_title_date_lines(body), _is_job_header):
        job = _parse_job_header(entry["header"])
        job["bullets"] = entry["bullets"]
        jobs.append(job)
    # Integrity signal (log only, never changes output): more dated header-looking
    # lines than parsed jobs means a role may have collapsed into another's bullets.
    dated_headers = sum(1 for l in body if not _is_bullet(l) and _is_job_header(l))
    if dated_headers > len(jobs):
        logger.warning(
            "[structurer] experience: %d dated header line(s) but %d job(s) parsed - a role may have collapsed",
            dated_headers, len(jobs),
        )
    return jobs


def _parse_projects(body: list) -> list:
    """Two shapes, handled in one pass: PDF 'Name | tech_stack' on one line;
    Word 'Name' then a separate tech-stack line. Bullet detection is
    glyph-independent (a project name in the PDF style always carries a '|', so
    even glyph-less PDFs don't confuse a bullet for a name)."""
    has_glyphs = any(_is_bullet(l) for l in body)
    projects = []
    cur = None

    def new_proj(name="", tech=None):
        nonlocal cur
        cur = {"name": name, "tech_stack": tech, "bullets": []}
        projects.append(cur)

    for line in body:
        if "|" in line and not _DATE_RANGE_RE.search(line):       # Name | tech_stack
            name, _, tech = line.partition("|")
            new_proj(name.strip(), tech.strip() or None)
        elif _is_bullet(line):
            if cur is None:
                new_proj()
            cur["bullets"].append(_strip_bullet(line))
        elif _starts_lower(line) and cur is not None:             # wrapped continuation
            if cur["bullets"]:
                cur["bullets"][-1] = (cur["bullets"][-1] + " " + line).strip()
            elif cur["tech_stack"]:
                cur["tech_stack"] = (cur["tech_stack"] + " " + line).strip()
            else:
                cur["name"] = (cur["name"] + " " + line).strip()
        elif not has_glyphs:                                      # glyph-less PDF bullet
            if cur is None:
                new_proj()
            cur["bullets"].append(line)
        elif cur is not None and not cur["bullets"] and cur["tech_stack"] is None:
            cur["tech_stack"] = line.strip()                      # Word style tech line
        else:
            new_proj(line.strip())                                # a new project name
    return projects


# --- education classification -----------------------------------------------
# Degree keywords. The 2-letter abbreviations REQUIRE a dot (b.s, m.a, …) so a
# state code or month ("Boston, MA", "MS", "March") is never read as a degree.
_DEGREE_RE = re.compile(
    r"\b(bachelors?|masters?|associate|diploma|doctorate|doctoral|undergraduate|postgraduate|"
    r"mba|m\.b\.a|ph\.?\s?d|bca|mca|"
    r"b\.?\s?tech|m\.?\s?tech|b\.?arch|b\.?\s?sc|m\.?\s?sc|"
    r"b\.s\.?|m\.s\.?|b\.a\.?|m\.a\.?|b\.e\.?|m\.e\.?)\b", re.IGNORECASE)
_INSTITUTION_RE = re.compile(
    r"\b(university|college|institute|institution|school|academy|polytechnic|universidad|iit|nit|iiit)\b",
    re.IGNORECASE)
# Secondary-school levels (common on Indian resumes) — treated like a degree so
# each opens its own education entry: "Class XII (CBSE)", "Intermediate", "SSC".
_SCHOOL_LEVEL_RE = re.compile(
    r"\b(class\s+(?:x|xi|xii|10|11|12)|higher\s+secondary|intermediate|matriculation|hsc|ssc|1[02]th)\b",
    re.IGNORECASE)
# A single graduation date — a plausible year, optionally with a month and an
# 'Expected/Present' qualifier. Restricted to 19xx/20xx so a course code like
# "CS 5304" isn't mistaken for a year.
_GRAD_YEAR = r"(?:19|20)\d{2}"
_SINGLE_DATE_RE = re.compile(
    rf"(?:expected|anticipated|graduating|graduated|present|current)?\s*(?:{_MONTH}\s*)?{_GRAD_YEAR}\b",
    re.IGNORECASE)
_EDU_DETAIL_RE = re.compile(
    r"^\s*(relevant\s+)?(coursework|courses|honou?rs|awards?|minor|thesis|dissertation|"
    r"activities|specialization|concentration|gpa|cgpa|grade|dean'?s\s+list|study\s+abroad)\b",
    re.IGNORECASE)
# A leading graduation-date label ("Expected", "Anticipated Graduation:",
# "Graduated") — stripped off the remainder once the date itself is extracted, so
# "Anticipated Graduation: Dec 2025" reduces to nothing (a pure date line) while
# "Expected May 2026 | GPA: 3.6" still yields the GPA.
_GRAD_LABEL_STRIP = re.compile(
    r"^\s*(?:(?:expected|anticipated|graduating|graduated)\b\s*)?"
    r"(?:(?:graduation|completion)\b\s*)?(?:date\b\s*)?[:\-]?\s*", re.IGNORECASE)
# A faculty/major like "College of Engineering" / "Institute of Design" — anchored,
# so a real school ("Birla Institute of Technology", proper noun first) is NOT
# matched. Kept with the degree, never treated as the awarding institution.
_FACULTY_RE = re.compile(r"^(college|institute|school|faculty|department)\s+of\b", re.IGNORECASE)
# An academic field / major, recognised by its tail noun ("Computer Science",
# "Business Analytics", "Information Systems"). When a 'Degree - X' line has no
# institution keyword, an X that ends like this is the MAJOR — kept with the
# degree — whereas a bare acronym ("MIT") is the school. Anchored at the end so a
# proper school name ("… Institute of Technology") is caught by the keyword test
# first and never reaches this.
_FIELD_TAIL_RE = re.compile(
    r"\b(science|sciences|engineering|studies|arts|management|administration|systems|"
    r"technology|mathematics|statistics|economics|commerce|computing|analytics|finance|"
    r"design|education|psychology|biology|chemistry|physics|informatics|accounting|"
    r"marketing|nursing|medicine|architecture|humanities|linguistics)\s*$", re.IGNORECASE)
# A strong in-line field separator.
_SEP_RE = re.compile(r"[|\t]|\s[–—\-]\s")
# A GPA / CGPA / percentage token anywhere in a string.
_GPA_PHRASE_RE = re.compile(
    r"(?:c?gpa|grade)\s*[:\-]?\s*\d(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?"
    r"|\d(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?"
    r"|\d{1,3}(?:\.\d+)?\s*%"
    r"|\d(?:\.\d+)?\s*c?gpa", re.IGNORECASE)
# Detail keywords for per-segment routing inside a pipe-delimited line.
_COURSEWORK_RE = re.compile(
    r"^(relevant\s+)?(coursework|courses|honou?rs|awards?|minor|thesis|dissertation|"
    r"activities|specialization|concentration|dean'?s\s+list|study\s+abroad)\b", re.IGNORECASE)


def _extract_any_date(text: str):
    """Pull a graduation date out of an education line — a range, a single
    'Mon YYYY'/'YYYY', or an 'Expected …'. Returns (grad_or_None, text_without_date).
    Spaces are collapsed but tabs survive as field separators, and a ', ,' gap
    left where an inline date was removed is tidied up."""
    start, end, rest = _extract_date_range(text)
    if start or end:
        grad = end if not start else (f"{start} – {end}" if end else start)
        return grad, rest
    m = _SINGLE_DATE_RE.search(text)
    if m and m.group(0).strip():
        grad = re.sub(r"[^\S\t]+", " ", m.group(0).strip())
        rest = re.sub(r"[^\S\t]+", " ", text[: m.start()] + " " + text[m.end():])
        rest = re.sub(r"\s*,\s*,\s*", ", ", rest).strip(" \t|,–—-")
        return grad, rest
    return None, text


def _edu_role(text: str) -> str:
    """Classify an education header line by what it carries."""
    has_deg = bool(_DEGREE_RE.search(text))
    has_inst = bool(_INSTITUTION_RE.search(text))
    if has_deg and has_inst:
        return "both"
    if has_deg:
        return "degree"
    if has_inst:
        return "institution"
    return "unknown"


def _split_on_separator(text: str) -> list:
    """Split a line on the strongest separator present (pipe, tab, or a spaced
    dash). Returns a single-element list when there's no separator."""
    if "|" in text:
        return [p.strip() for p in text.split("|") if p.strip()]
    if "\t" in text:
        return [p.strip() for p in text.split("\t") if p.strip()]
    dparts = [p.strip() for p in re.split(r"\s+[–—\-]\s+", text) if p.strip()]
    return dparts if len(dparts) >= 2 else [text.strip()]


def _split_degree_institution(text: str):
    """Split a combined 'Degree | Institution [| GPA | Location]' line. A
    faculty/major phrase ('College of Engineering', 'Institute of Design') is kept
    with the DEGREE, never treated as the school. Returns (degree, rest) where rest
    is the institution segment plus any GPA/location for the caller to absorb."""
    parts = _split_on_separator(text)
    if len(parts) < 2:
        return text, ""
    deg = next((p for p in parts if _DEGREE_RE.search(p)), parts[0])
    others = [p for p in parts if p is not deg]
    faculty = [p for p in others if _FACULTY_RE.match(p)]
    if faculty:
        deg = "  -  ".join([deg] + faculty)
    rest = [p for p in others if p not in faculty]
    if not rest:
        return deg, ""
    inst = next((p for p in rest if _INSTITUTION_RE.search(p)), None)
    if inst is None:
        # No institution keyword in the remainder. A segment that names an academic
        # field ("Computer Science") is the MAJOR — fold it into the degree so the
        # real school (usually the next line) isn't pushed into a phantom entry. A
        # keyword-less acronym like "MIT" has no field tail and stays the school.
        field = next((p for p in rest if _FIELD_TAIL_RE.search(p)), None)
        if field is not None:
            deg = "  -  ".join([deg, field])
            rest = [p for p in rest if p is not field]
            if not rest:
                return deg, ""
        inst = rest[0]
    extras = [p for p in rest if p is not inst]
    return deg, (inst + ("  |  " + "  |  ".join(extras) if extras else ""))


def _absorb_meta(entry: dict, line: str) -> str:
    """Peel GPA / location / coursework out of a (possibly pipe-delimited) trailing
    education line into the entry. Returns the leftover institution-ish text."""
    segs = _split_pipes(line) if "|" in line else [line]
    leftover = []
    for seg in segs:
        seg = seg.strip()
        if not seg:
            continue
        if _COURSEWORK_RE.match(seg):
            entry["details"].append(seg)
        elif entry["gpa"] is None and _GPA_PHRASE_RE.search(seg) and not _INSTITUTION_RE.search(seg):
            entry["gpa"] = seg
        elif entry["location"] is None and _looks_like_location(seg):
            entry["location"] = seg
        else:
            leftover.append(seg)
    return "  |  ".join(leftover)


def _peel_degree_meta(entry: dict):
    """Pull an inline GPA/percentage out of the degree text into the gpa field and
    tidy any ', ,' / dangling commas left behind."""
    deg = entry["degree"]
    if entry["gpa"] is None:
        m = _GPA_PHRASE_RE.search(deg)
        if m:
            entry["gpa"] = m.group(0).strip()
            deg = deg[: m.start()] + " " + deg[m.end():]
    deg = re.sub(r"\s*,\s*,\s*", ", ", re.sub(r"[^\S\t]+", " ", deg))
    entry["degree"] = deg.strip(" ,")


def _parse_education(body: list) -> list:
    """Parse education across the layouts seen in real resumes:
      * 'Degree   GradDate' then 'Institution'         (single dates, two lines)
      * 'Degree' / 'GradDate' / 'Institution'          (date on its own line)
      * 'Institution  GradDate' then 'Degree'          (institution-first)
      * 'Degree | Institution  Date' (or ' - ')        (combined on one line)
    Single graduation dates (not just ranges) become graduation_date, GPA and
    location are pulled out, and every degree opens its own entry rather than
    collapsing into bullets."""
    entries = []
    cur = None

    def start_entry():
        nonlocal cur
        cur = {"degree": "", "institution": "", "location": None,
               "graduation_date": None, "gpa": None, "details": []}
        entries.append(cur)
        return cur

    for line in body:
        is_b = _is_bullet(line)
        raw = (_strip_bullet(line) if is_b else line).strip()
        if not raw or not re.search(r"[A-Za-z0-9]", raw):
            continue  # blank or a lone separator like "|"

        # 1. Detail lines (Coursework / Honors / Dean's List / Study Abroad / GPA /
        #    glyph bullets) stay with the current entry, kept verbatim.
        if cur is not None and (is_b or _EDU_DETAIL_RE.match(raw)):
            _absorb_detail(cur, raw)
            continue

        grad, rest = _extract_any_date(raw)
        rest = _GRAD_LABEL_STRIP.sub("", rest).strip(" :\t|,–—-")

        # 2. A line that is ONLY a date (a bare year range, or a date + an
        #    'Expected/Graduation' label) belongs to the current entry — handled
        #    before the wrapped-continuation rule so a digit-leading date is never
        #    glued onto the previous field.
        if not rest:
            if cur is None:
                start_entry()
            if grad and not cur["graduation_date"]:
                cur["graduation_date"] = grad
            continue

        has_deg = bool(_DEGREE_RE.search(rest) or _SCHOOL_LEVEL_RE.search(rest))
        has_inst = bool(_INSTITUTION_RE.search(rest))

        # 3. A wrapped continuation: starts with a LOWERCASE letter (a digit-led
        #    line is a date/grade, already handled) with no degree/inst/date signal.
        if cur is not None and raw[:1].islower() and not has_deg and not has_inst and not grad:
            if cur["details"]:
                cur["details"][-1] = (cur["details"][-1] + " " + raw).strip()
            elif cur["institution"]:
                cur["institution"] = (cur["institution"] + " " + raw).strip()
            elif cur["degree"]:
                cur["degree"] = (cur["degree"] + " " + raw).strip()
            else:
                cur["degree"] = raw
            continue

        # 4. Open a NEW entry on a real degree, an institution when the current
        #    entry already has one, OR an unrecognised line that carries its OWN
        #    date when the current entry already has a date (a degree whose keyword
        #    we don't know — e.g. just "Computer Science  Aug 2018 - Aug 2022").
        #    NEVER on an unknown trailing line without a fresh date — that prevents
        #    phantom entries from locations / honours / GPA tails.
        if cur is None:
            start_entry()
        elif has_deg and cur["degree"]:
            start_entry()
        elif has_inst and not has_deg and cur["institution"]:
            start_entry()
        elif (grad and cur["graduation_date"] and not has_deg and not has_inst
              and not raw[:1].islower() and not _looks_like_location(rest)):
            start_entry()

        grad_stored = False
        if grad and not cur["graduation_date"]:
            cur["graduation_date"] = grad
            grad_stored = True

        # 5. Place the content.
        if has_deg:
            if _SEP_RE.search(rest):  # may also carry institution / GPA / location
                deg, inst = _split_degree_institution(rest)
                cur["degree"] = (cur["degree"] + " " + deg).strip() if cur["degree"] else deg
                if inst:
                    if "|" not in inst and not _INSTITUTION_RE.search(inst) and _looks_like_location(inst) and cur["location"] is None:
                        cur["location"] = inst          # "DEGREE | USA" — a bare location, not the school
                    elif cur["institution"]:
                        _absorb_detail(cur, inst)
                    else:
                        cur["institution"] = _absorb_education_line(cur, inst)
            else:
                cur["degree"] = (cur["degree"] + " " + rest).strip() if cur["degree"] else rest
            _peel_degree_meta(cur)
        elif has_inst:
            if cur["institution"]:
                _absorb_detail(cur, rest)
            else:
                cur["institution"] = _absorb_education_line(cur, rest)
        else:  # unknown remainder — route it, never fabricate a degree
            if _looks_like_location(rest) and cur["location"] is None:
                cur["location"] = rest
            elif not cur["degree"]:
                if _SEP_RE.search(rest):                # e.g. "COMPUTER SCIENCE ENG | IND"
                    leftover = _absorb_meta(cur, rest)  # peels the trailing location/GPA
                    cur["degree"] = re.sub(r"\s*\|\s*", " ", leftover).strip() or rest
                else:
                    cur["degree"] = rest
            elif not cur["institution"]:
                cur["institution"] = _absorb_education_line(cur, rest)
            else:
                # Keep the original line (with its date) if a fresh date couldn't
                # be stored, so a graduation year is never silently dropped.
                _absorb_detail(cur, raw if (grad and not grad_stored) else rest)

    return entries


def _absorb_education_line(entry: dict, line: str) -> str:
    """The institution line — pull GPA / location / coursework out and return the
    cleaned institution name ('Institution | GPA | Location' or
    'Institution, City, ST')."""
    if "|" in line:
        leftover = _absorb_meta(entry, line)
        segs = [s.strip() for s in leftover.split("|") if s.strip()]
        if len(segs) > 1:                         # keep any extra segments as details
            entry["details"].extend(segs[1:])
        return segs[0] if segs else ""
    # No pipes (Word style). Try to peel a trailing 'City, ST' / 'City, Country'.
    m = re.search(r",\s*([A-Za-z .]+,\s*[A-Z]{2}|[A-Za-z .]+,\s*[A-Za-z ]+)$", line)
    if m:
        entry["location"] = m.group(1).strip()
        return line[: m.start()].strip()
    return line


def _absorb_detail(entry: dict, line: str):
    """A trailing education line (Coursework / Honors / a GPA / a stray location).
    Peel GPA & location into their own fields; keep the rest as a detail — never a
    separate degree."""
    leftover = _absorb_meta(entry, line)
    if leftover.strip():
        entry["details"].append(leftover.strip())


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
        if not segs:
            continue  # a line that's only pipes/whitespace carries no cert
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
        for k, v in value.items():
            if isinstance(k, str):
                yield k                      # skills category labels live in the keys
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
        "contact": {"phone": None, "email": None, "email_label": None,
                    "linkedin": None, "linkedin_label": None,
                    "github": None, "github_label": None,
                    "location": None, "links": []},
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

    # A bullet glyph extracted onto its OWN line (a common PDF artifact) is merged
    # with the text on the following line; leftover junk/box glyphs are stripped.
    merged, k = [], 0
    while k < len(lines):
        if _is_lone_bullet(lines[k]):
            if k + 1 < len(lines) and not _is_lone_bullet(lines[k + 1]):
                merged.append("• " + lines[k + 1])
                k += 2
            else:
                k += 1  # a stray lone bullet with no following text — drop it
        else:
            merged.append(lines[k])
            k += 1
    lines = [t for t in (_sanitize(l).strip() for l in merged) if t]
    if not lines:
        return data

    content_lines = list(lines)  # for the completeness guard

    # 2. Header block: name, then headline + contact, up to the first section.
    #
    # The header zone is everything between the name and the first real section.
    # We must NOT end it at any ALL-CAPS line: a job title like "AI/ML ENGINEER"
    # or "DATA SCIENTIST" sits right under the name and trips _looks_like_heading,
    # which would strand the title + contact line in a body section (rendering it
    # below Projects). So we extend the header zone to the first KNOWN section, and
    # only let a *generic* ALL-CAPS heading end it when it isn't part of the
    # name/title/contact cluster — decided by looking ahead for a contact line.
    # Line 1 is the name. If it's "Name | Role" (a pipe-separated headline on the
    # same line), split the role off into the headline instead of the name.
    name_line = lines[0]
    extra_headline = None
    if "|" in name_line:
        nparts = [p.strip() for p in name_line.split("|") if p.strip()]
        data["name"] = nparts[0] if nparts else name_line
        if len(nparts) > 1:
            extra_headline = " ".join(nparts[1:]).strip()
    else:
        data["name"] = name_line

    # Does a contact line appear in the top region before any known section?
    has_top_contact = False
    j = 1
    while j < len(lines) and j < 8 and _heading_type(lines[j]) is None:
        if _line_has_contact(lines[j]):
            has_top_contact = True
            break
        j += 1

    idx = 1
    preamble = []
    while idx < len(lines):
        line = lines[idx]
        if _heading_type(line) is not None:
            break  # a real, known section starts the body
        if _looks_like_heading(line):
            # Generic ALL-CAPS heading. Keep it in the header only while we're
            # still above the contact line of a header that has one; otherwise it
            # is a real section (e.g. "AWARDS" right under the name).
            already_have_contact = any(_line_has_contact(p) for p in preamble)
            if not (has_top_contact and not already_have_contact):
                break
        preamble.append(line)
        idx += 1

    # Split the header zone into contact line(s) and headline text. Gather ALL
    # contact-bearing lines (contact may be split across lines) and drop a stray
    # date-only line so it can't become the headline.
    contact_lines = []
    headline_parts = []
    for p in preamble:
        if _line_has_contact(p):
            contact_lines.append(p)
        elif _DATE_RANGE_RE.search(p) and len(p.split()) <= 4:
            continue
        else:
            headline_parts.append(p)
    headline_bits = ([extra_headline] if extra_headline else []) + headline_parts
    if headline_bits:
        joined = " ".join(headline_bits).strip()
        # A short tagline is a headline; a long sentence is really the summary.
        # Some resumes drop the summary right under the contact with no heading —
        # keep it readable as the summary instead of a giant centered headline.
        if len(joined.split()) > 16:
            data["summary"] = joined
        else:
            data["headline"] = joined
    data["contact"] = _parse_contact(" | ".join(contact_lines), embedded)

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
