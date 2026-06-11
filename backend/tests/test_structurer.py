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
from docx import Document
from docx.oxml.ns import qn

import structurer as S
from formatters.compact_ats import format_compact
from parsers.pdf_parser import extract_text_from_pdf
from parsers.docx_parser import extract_text_from_docx

# Real candidate resumes live in ../DemoResumes (drop more in to expand coverage).
DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "DemoResumes")
DEMO_FILES = sorted(glob.glob(os.path.join(DEMO_DIR, "*.pdf")) + glob.glob(os.path.join(DEMO_DIR, "*.docx")))


def _toks(s):
    return [t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split() if t]


def _docx_all_tokens(path):
    """Every token in the rendered DOCX — visible text PLUS hyperlink targets
    (a 'LinkedIn' link keeps its URL in the relationship, not in the text)."""
    doc = Document(path)
    out = set()
    for node in doc.element.body.iter(qn("w:t")):
        out |= set(_toks(node.text))
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype:
            out |= set(_toks(rel.target_ref))
    return out


# ── unit: heading detection ──────────────────────────────────────────────────

def test_allcaps_education_content_is_not_a_heading():
    # An ALL-CAPS institution / degree / GPA line inside EDUCATION must NOT be read
    # as a section heading — doing so splits the section and scatters the rows.
    assert not S._looks_like_heading("UNIVERSITY OF NORTH TEXAS")
    assert not S._looks_like_heading("VELLORE INSTUTITE OF TECHNOLOGY")  # typo + 'OF'
    assert not S._looks_like_heading("CGPA: 8.5/10")
    assert not S._looks_like_heading("CLASS XII 2020")
    # genuine word-only headings still detected
    assert S._looks_like_heading("ACHIEVEMENTS")
    assert S._looks_like_heading("AWARDS")


def test_education_allcaps_institutions_do_not_split_section():
    # Real layout: degree line, then the school in ALL CAPS on its own line.
    raw = (
        "Karthik\nkarthik@example.com\n\n"
        "EDUCATION\n"
        "Master of Science in Computer and information science May 2025\n"
        "UNIVERSITY OF NORTH TEXAS\n"
        "Bachelors in Computer Science and Engineering May 2023\n"
        "VELLORE INSTUTITE OF TECHNOLOGY\n"
    )
    data = S.structure_resume(raw)
    assert len(data["education"]) == 2
    assert data["education"][0]["institution"] == "UNIVERSITY OF NORTH TEXAS"
    assert data["education"][1]["institution"] == "VELLORE INSTUTITE OF TECHNOLOGY"
    # nothing leaked into a fabricated section
    assert not data["additional_sections"]


def test_education_degree_dash_major_keeps_one_entry():
    # "Degree - Major" then the school: the major stays with the degree and the
    # school (whose city must not eat the whole name) is the institution — one entry.
    edus = S._parse_education([
        "Master of Science - Computer Science Jan 2024 – Dec 2025",
        "New Jersey Institute of Technology (NJIT) – Newark, NJ | GPA:3.35/4.0",
    ])
    assert len(edus) == 1
    assert "Computer Science" in edus[0]["degree"]
    assert "New Jersey Institute of Technology" in edus[0]["institution"]
    assert "8.5" not in (edus[0]["gpa"] or "") and edus[0]["gpa"]  # GPA captured


def test_known_and_keyword_headings():
    assert S._heading_type("PROFESSIONAL SUMMARY") == "summary"
    assert S._heading_type("Work EXPERIENCE") == "experience"
    assert S._heading_type("TECHNICAL SKILLS") == "skills"
    # bespoke ALL-CAPS heading routed by keyword fallback
    assert S._heading_type("PROJECT MANAGEMENT SKILLS") == "skills"
    # a Title-Case job title must NOT be mistaken for a section
    assert S._heading_type("Project Manager") is None


# ── unit: header with an ALL-CAPS job title under the name ───────────────────

def test_allcaps_headline_and_contact_are_captured_not_stranded():
    # Regression: an ALL-CAPS title like "AI/ML ENGINEER" under the name used to
    # be mistaken for a section heading, stranding the title + contact line in a
    # body section that rendered below Projects.
    raw = "\n".join([
        "RUTVIK DESHMUKH",
        "AI/ML ENGINEER",
        "+1 (551)-344-8461 | rutvik@gmail.com | LinkedIn | GitHub | MD, USA",
        "PROFESSIONAL SUMMARY",
        "AI/ML engineer with experience building systems.",
    ])
    data = S.structure_resume(raw)
    assert data["name"] == "RUTVIK DESHMUKH"
    assert data["headline"] == "AI/ML ENGINEER"
    assert data["contact"]["email"] == "rutvik@gmail.com"
    assert data["contact"]["location"] == "MD, USA"
    # title/contact must NOT be stranded in an additional (below-Projects) section
    blob = " ".join(
        (s.get("heading", "") + " " + " ".join(s.get("items", []) or []) + " " + (s.get("text") or ""))
        for s in data["additional_sections"]
    )
    assert "AI/ML ENGINEER" not in blob
    assert "rutvik@gmail.com" not in blob


def test_generic_allcaps_section_right_after_name_is_still_a_section():
    # The header fix must not over-absorb: a real ALL-CAPS section immediately
    # under the name (no contact line above it) stays a section, not a headline.
    raw = "\n".join([
        "JANE DOE",
        "AWARDS",
        "Employee of the Year 2024",
        "PROFESSIONAL SUMMARY",
        "Did good work.",
    ])
    data = S.structure_resume(raw)
    assert data["headline"] is None
    assert any(s.get("heading", "").lower() == "awards" for s in data["additional_sections"])


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


def test_two_jobs_with_title_above_date_line_stay_separate():
    # Word layout: each role's TITLE sits on its own line, then "Company  Dates".
    # The second role used to collapse into the first role's bullets ("kept 1 of 2").
    jobs = S._parse_experience([
        "Senior Engineer",
        "Acme Corp\t2022 - Present",
        "• Led the platform team",
        "Junior Engineer",
        "Beta Inc\t2019 - 2021",
        "• Built internal tools",
    ])
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Senior Engineer"
    assert jobs[0]["company"] == "Acme Corp"
    assert jobs[0]["bullets"] == ["Led the platform team"]
    assert jobs[1]["title"] == "Junior Engineer"
    assert jobs[1]["company"] == "Beta Inc"
    assert jobs[1]["bullets"] == ["Built internal tools"]


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

def test_education_single_date_two_entries():
    # Regression: 'Degree  GradDate' / 'Institution' with SINGLE dates (not ranges).
    # Used to leak the date into the degree and demote the 2nd degree to bullets.
    edus = S._parse_education([
        "Masters in Data Analytics and Engineering Dec 2025",
        "George Mason University",
        "Bachelor of Technology in Computer Science and Engineering May 2023",
        "Jawaharlal Nehru Technological University",
    ])
    assert len(edus) == 2
    assert edus[0]["degree"] == "Masters in Data Analytics and Engineering"
    assert edus[0]["graduation_date"] == "Dec 2025"
    assert edus[0]["institution"] == "George Mason University"
    assert edus[1]["degree"].startswith("Bachelor of Technology")
    assert edus[1]["graduation_date"] == "May 2023"
    assert edus[1]["institution"] == "Jawaharlal Nehru Technological University"
    assert edus[0]["details"] == [] and edus[1]["details"] == []


def test_education_date_on_its_own_line_with_gpa_location_coursework():
    edus = S._parse_education([
        "Master of Science in Information Systems",
        "Aug 2024 – Dec 2025",
        "University of Maryland, Robert H. Smith School of Business | GPA: 3.5/4.0 | College Park, MD",
        "Bachelor of Technology in Computer Science",
        "Aug 2020 – Jun 2024",
        "Gujarat Technological University | GPA: 3.78/4.0 | Ahmedabad, India | Relevant Coursework: ML, NLP",
    ])
    assert len(edus) == 2
    assert edus[0]["graduation_date"] == "Aug 2024 – Dec 2025"
    assert edus[0]["gpa"] == "GPA: 3.5/4.0"
    assert edus[0]["location"] == "College Park, MD"
    assert "University of Maryland" in edus[0]["institution"]
    assert edus[1]["gpa"] == "GPA: 3.78/4.0"
    assert any("Coursework" in d for d in edus[1]["details"])


def test_education_institution_first_ordering():
    edus = S._parse_education([
        "KENNESAW STATE UNIVERSITY May 2025",
        "Masters in computer science",
        "SRM University April 2022",
        "Electronics and communication engineering",
    ])
    assert len(edus) == 2
    assert edus[0]["institution"] == "KENNESAW STATE UNIVERSITY"
    assert edus[0]["graduation_date"] == "May 2025"
    assert "computer science" in edus[0]["degree"].lower()
    assert edus[1]["institution"] == "SRM University"


def test_education_degree_pipe_institution_one_line():
    edus = S._parse_education([
        "Master's in Science in Computer Science | The University of Texas at Arlington Dec 2024",
        "Bachelor's of Engineering | Gujarat Technological University July 2022",
    ])
    assert len(edus) == 2
    assert "Computer Science" in edus[0]["degree"]
    assert "University of Texas" in edus[0]["institution"]
    assert edus[0]["graduation_date"] == "Dec 2024"
    assert "Gujarat Technological University" in edus[1]["institution"]


def test_state_code_not_mistaken_for_a_degree():
    # 'Boston, MA' must NOT be split off as an M.A. degree.
    edus = S._parse_education([
        "Masters in Quantitative Finance Dec 2024",
        "Northeastern University | Boston, MA",
    ])
    assert len(edus) == 1
    assert "Northeastern University" in edus[0]["institution"]
    assert edus[0]["graduation_date"] == "Dec 2024"


def test_education_bare_year_range_on_own_line():
    # A digit-leading date line must be extracted, not glued onto the degree.
    edus = S._parse_education([
        "Master of Business Administration",
        "2022 - 2024",
        "Harvard Business School | GPA: 3.7 | Boston, MA",
    ])
    assert len(edus) == 1
    assert edus[0]["graduation_date"] == "2022 – 2024"
    assert "2022" not in edus[0]["degree"]
    assert edus[0]["gpa"] == "GPA: 3.7" and edus[0]["location"] == "Boston, MA"


def test_education_keywordless_school_pipe_line_splits():
    # "MIT" has no university/college keyword but the pipe line must still split.
    edus = S._parse_education(["B.S. Mechanical Engineering | MIT | 3.9/4.0 | Cambridge, MA"])
    assert len(edus) == 1
    assert edus[0]["institution"] == "MIT"
    assert edus[0]["gpa"] == "3.9/4.0"
    assert edus[0]["location"] == "Cambridge, MA"
    assert "MIT" not in edus[0]["degree"]


def test_education_faculty_of_stays_with_degree():
    # "Institute of Design" is the major, NOT the school; the real school follows.
    edus = S._parse_education([
        "Master of Science - Institute of Design  Dec 2025",
        "Illinois Tech",
        "Bachelor of Engineering  May 2021",
        "Birla Institute of Technology",
    ])
    assert len(edus) == 2
    assert edus[0]["institution"] == "Illinois Tech"
    assert "Institute of Design" in edus[0]["degree"]
    assert edus[1]["institution"] == "Birla Institute of Technology"


def test_education_trailing_lines_never_make_phantom_entries():
    # Honors / a stray location / "Anticipated Graduation" must fold into the one
    # entry, never fabricate a second degree.
    edus = S._parse_education([
        "Bachelor of Arts in Economics",
        "Yale University | New Haven, CT",
        "May 2024",
        "Dean's List (all semesters)",
        "Honors: Magna Cum Laude",
        "Evanston, IL",
    ])
    assert len(edus) == 1
    assert edus[0]["graduation_date"] == "May 2024"
    assert edus[0]["institution"] == "Yale University"
    assert len(edus[0]["details"]) >= 2  # the honors lines kept as details


def test_education_indian_secondary_school_levels():
    edus = S._parse_education([
        "Class XII (CBSE), 2018, 88.4%",
        "Delhi Public School, New Delhi",
        "Class X (CBSE), 2016, 9.6 CGPA",
    ])
    assert len(edus) == 2
    assert edus[0]["graduation_date"] == "2018" and "88.4%" in (edus[0]["gpa"] or "")
    assert "88.4%" not in edus[0]["degree"]


def test_education_degree_with_date_and_country_then_institution():
    # 'DEGREE  Date | Country' then 'Institution' — the country is a LOCATION (not
    # the school), and a keyword-less degree name still aligns to its own school.
    edus = S._parse_education([
        "MASTERS IN INFORMATION STUDIES Aug 2023 - Dec 2025 | USA",
        "Trine University",
        "COMPUTER SCIENCE ENGINEERING Jun 2018 - Feb 2022 | IND",
        "Shadan College Of Engineering",
    ])
    assert len(edus) == 2
    assert edus[0]["degree"] == "MASTERS IN INFORMATION STUDIES"
    assert edus[0]["institution"] == "Trine University"
    assert edus[0]["location"] == "USA"
    assert edus[0]["graduation_date"] == "Aug 2023 – Dec 2025"
    assert edus[1]["degree"] == "COMPUTER SCIENCE ENGINEERING"
    assert edus[1]["institution"] == "Shadan College Of Engineering"
    assert edus[1]["location"] == "IND"


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
    rendered_tokens = _docx_all_tokens(out_path)

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
