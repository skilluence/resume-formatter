"""Tests for the rule-based structurer (structurer.py) and the full
parse -> build -> re-read pipeline.

Two guarantees the client cares about:
  1. Structure: the common resume shapes (both Skilluence templates, PDF & Word)
     parse into the right fields.
  2. Fidelity: NOTHING from the source is lost on the way to the final DOCX.

Pure-function + filesystem tests. No network, no OpenAI, no API key.
"""

import os
import re
import glob
import tempfile

import pytest

import structurer as S
from formatters.compact_ats import format_compact
from parsers.pdf_parser import extract_text_from_pdf
from parsers.docx_parser import extract_text_from_docx

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "demoResume")
DEMO_FILES = sorted(glob.glob(os.path.join(DEMO_DIR, "*.pdf")) + glob.glob(os.path.join(DEMO_DIR, "*.docx")))


def _toks(s):
    return [t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split() if t]


# ── unit: heading detection ──────────────────────────────────────────────────

def test_known_and_keyword_headings():
    assert S._heading_type("PROFESSIONAL SUMMARY") == "summary"
    assert S._heading_type("Work EXPERIENCE") == "experience"
    assert S._heading_type("TECHNICAL SKILLS") == "skills"
    # bespoke ALL-CAPS heading routed by keyword fallback
    assert S._heading_type("PROJECT MANAGEMENT SKILLS") == "skills"
    # a Title-Case job title must NOT be mistaken for a section
    assert S._heading_type("Project Manager") is None


# ── unit: experience headers across templates ────────────────────────────────

def test_pdf_style_job_line():
    job = S._parse_single_job_line("Data Analyst | Wipro Limited Jul 2025 – Present | San Jose, CA")
    assert job["title"] == "Data Analyst"
    assert job["company"] == "Wipro Limited"
    assert job["location"] == "San Jose, CA"
    assert job["start_date"] == "Jul 2025" and job["end_date"] == "Present"


def test_word_style_tab_job_line():
    job = S._parse_single_job_line("MetLife / Machine Learning Engineer\tJan 2021 – Jul 2023 | IND")
    assert job["company"] == "MetLife"
    assert "Machine Learning Engineer" in job["title"]
    assert job["location"] == "IND"
    assert job["start_date"] == "Jan 2021" and job["end_date"] == "Jul 2023"


def test_title_on_its_own_line():
    # "Company <tab> Dates" then a separate "Title" line
    jobs = S._parse_experience(["DTC\tJun 2025 – Dec 2025", "Project Manager", "• Did things"])
    assert len(jobs) == 1
    assert jobs[0]["company"] == "DTC"
    assert jobs[0]["title"] == "Project Manager"
    assert jobs[0]["bullets"] == ["Did things"]


# ── unit: bullets without a glyph ────────────────────────────────────────────

def test_glyphless_bullets_are_not_split_into_projects():
    body = [
        "My Project | Python, SQL",
        "Built a thing that did something useful and measurable",
        "improving an outcome by 30%.",
        "Designed another component for the same project",
    ]
    projects = S._parse_projects(body)
    assert len(projects) == 1                       # one project, not four
    assert projects[0]["name"] == "My Project"
    assert projects[0]["tech_stack"] == "Python, SQL"
    assert len(projects[0]["bullets"]) == 2          # 2nd & 3rd lines joined as one bullet


# ── unit: education GPA goes to its own toggle-able field ─────────────────────

def test_education_gpa_and_details():
    edus = S._parse_education([
        "Master of Science in Information Systems Aug 2024 – Dec 2025",
        "University of Maryland | GPA: 3.5/4.0 | College Park, MD | Relevant Coursework: ML, NLP",
    ])
    assert len(edus) == 1
    e = edus[0]
    assert e["gpa"] == "GPA: 3.5/4.0"
    assert e["location"] == "College Park, MD"
    assert "University of Maryland" in e["institution"]
    assert any("Coursework" in d for d in e["details"])


# ── unit: skills categories + wrapped continuation ───────────────────────────

def test_skills_categories_and_continuation():
    skills = S._parse_skills([
        "Programming & Analysis: Python, SQL,",
        "PL/SQL, Pandas",
        "Cloud & Tools: AWS, Snowflake",
    ])
    assert skills["Programming & Analysis"] == ["Python", "SQL", "PL/SQL", "Pandas"]
    assert skills["Cloud & Tools"] == ["AWS", "Snowflake"]


# ── unit: the never-drop recovery net ────────────────────────────────────────

def test_recovery_net_catches_a_dropped_line():
    # A content line not represented anywhere in the parsed data must be
    # recovered into "Additional Information" rather than silently lost.
    data = {
        "name": "X", "headline": None,
        "contact": {"phone": None, "email": None, "linkedin": None, "github": None, "location": None, "links": []},
        "summary": None, "skills": {}, "experience": [], "projects": [],
        "education": [], "certifications": [], "additional_sections": [],
    }
    out = S._recover_dropped(data, ["X", "an orphaned line zubble frobnicate"])
    items = [i for s in out["additional_sections"] for i in s.get("items", [])]
    assert any("zubble" in i and "frobnicate" in i for i in items)


# ── job headers across every separator + the bullet-as-header regression ─────

def test_bullet_with_inline_year_range_is_not_a_job_header():
    jobs = S._parse_experience([
        "Engineer | Acme \tJan 2020 – Dec 2021 | USA",
        "• Led a project across the 2020 – 2021 cycle, improving throughput by 40%.",
        "• Shipped another thing entirely.",
    ])
    assert len(jobs) == 1                       # the bullets did NOT split into fake jobs
    assert len(jobs[0]["bullets"]) == 2
    assert jobs[0]["title"] == "Engineer" and jobs[0]["company"] == "Acme"


def test_job_header_separators_and_location():
    # pipe, title-first, location lifted out
    j = S._parse_single_job_line("AI/ML Engineer | Scale AI \tJuly 2025 – Present | USA")
    assert (j["title"], j["company"], j["location"]) == ("AI/ML Engineer", "Scale AI", "USA")
    # dash separators with a trailing location
    j = S._parse_single_job_line("Platform Engineer – Capital One – LA, USA\tFeb 2024 – Present")
    assert (j["title"], j["company"], j["location"]) == ("Platform Engineer", "Capital One", "LA, USA")
    # slash => company first, abbreviation location
    j = S._parse_single_job_line("MetLife / Machine Learning Engineer\tJan 2021 – Jul 2023 | IND")
    assert j["company"] == "MetLife" and "Machine Learning Engineer" in j["title"] and j["location"] == "IND"
    # a title alone on the next line becomes the title, the lone label the company
    jobs = S._parse_experience(["DTC\tJun 2025 – Dec 2025", "Project Manager", "• Did things"])
    assert jobs[0]["company"] == "DTC" and jobs[0]["title"] == "Project Manager"


# ── integration: every demo resume parses and loses nothing end-to-end ───────

@pytest.mark.skipif(not DEMO_FILES, reason="no demo resumes present")
@pytest.mark.parametrize("path", DEMO_FILES, ids=[os.path.basename(p) for p in DEMO_FILES])
def test_no_data_lost_through_full_pipeline(path, tmp_path):
    ext = os.path.splitext(path)[1].lower()
    raw = extract_text_from_pdf(path) if ext == ".pdf" else extract_text_from_docx(path)

    resume = S.structure_resume(raw)
    assert resume["name"], "candidate name must be captured"

    out_path = str(tmp_path / "out.docx")
    format_compact(resume, out_path)
    rendered_tokens = set(_toks(extract_text_from_docx(out_path)))

    # every content token from the source must appear in the final DOCX
    missing = []
    for line in [l.strip() for l in raw.splitlines() if l.strip()][1:]:
        if line.lower().startswith("embedded links:"):
            break
        if S._heading_type(line) or S._looks_like_heading(line):
            continue  # section headings are structure, not data
        body = S._strip_bullet(line) if S._is_bullet(line) else line
        for t in _toks(body):
            if t not in rendered_tokens:
                missing.append(t)
    assert not missing, f"tokens lost before the final DOCX: {missing[:15]}"
