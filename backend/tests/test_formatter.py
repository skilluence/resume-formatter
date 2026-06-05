"""Tests for the DOCX formatter (formatters/compact_ats.py): hyperlink safety,
section reordering, and resilience to malformed/edited resume data.

Each test renders a real .docx to a temp dir and re-reads its text (including
hyperlink runs), so you can see exactly what lands in the document.
"""

from docx import Document
from docx.oxml.ns import qn

from formatters.compact_ats import format_compact, _resolve_section_order


def _docx_text(path):
    """All visible text in the document, including hyperlink runs and headers."""
    body = Document(path).element.body
    return " ".join((t.text or "") for t in body.iter(qn("w:t")))


def _base_resume(**over):
    r = {
        "name": "Jane Doe", "headline": "Engineer",
        "contact": {"phone": None, "email": None, "linkedin": None, "github": None, "location": None, "links": []},
        "summary": None, "skills": {}, "experience": [], "projects": [],
        "education": [], "certifications": [], "additional_sections": [],
    }
    r.update(over)
    return r


# ── hyperlink / contact safety ───────────────────────────────────────────────

def test_blank_and_whitespace_links_never_crash(tmp_path):
    contact = {
        "phone": "  ", "email": "   ", "linkedin": "  ", "github": "",
        "location": "NYC",
        "links": [
            {"label": "", "url": ""},            # nothing — skipped
            {"label": "Portfolio", "url": ""},   # label kept, no link
            {"label": "", "url": "example.com"}, # url becomes the label
        ],
    }
    out = str(tmp_path / "x.docx")
    format_compact(_base_resume(contact=contact), out)   # must not raise
    text = _docx_text(out)
    assert "NYC" in text
    assert "Portfolio" in text                  # label preserved even with no URL
    assert "example.com" in text


def test_invalid_link_degrades_without_crashing(tmp_path):
    contact = {"phone": None, "email": None, "linkedin": None, "github": None, "location": None,
               "links": [{"label": "Site", "url": "ht!tp://%%% not a url"}]}
    out = str(tmp_path / "y.docx")
    format_compact(_base_resume(contact=contact), out)   # must not raise
    assert "Site" in _docx_text(out)            # the visible word is never dropped


def test_none_name_does_not_crash(tmp_path):
    out = str(tmp_path / "n.docx")
    format_compact(_base_resume(name=None), out)         # must not raise


# ── section reordering ───────────────────────────────────────────────────────

def test_section_order_reorders_body(tmp_path):
    r = _base_resume(
        summary="A summary.",
        skills={"Lang": ["Python"]},
        projects=[{"name": "Proj", "tech_stack": None, "bullets": ["did x"]}],
        education=[{"degree": "BS CS", "institution": "MIT", "location": None,
                    "graduation_date": "2020", "gpa": None, "details": []}],
        section_order=["education", "projects", "skills"],
    )
    out = str(tmp_path / "z.docx")
    format_compact(r, out)
    text = _docx_text(out)
    i_summary = text.find("PROFESSIONAL SUMMARY")
    i_edu = text.find("EDUCATION")
    i_proj = text.find("PROJECTS")
    i_skills = text.find("TECHNICAL SKILLS")
    # Summary stays pinned first, then the requested order: education < projects < skills
    assert i_summary != -1 and i_summary < i_edu < i_proj < i_skills


def test_section_order_omission_still_renders_everything(tmp_path):
    r = _base_resume(
        skills={"Lang": ["Python"]},
        education=[{"degree": "BS", "institution": "MIT", "location": None,
                    "graduation_date": "2020", "gpa": None, "details": []}],
        section_order=["skills"],   # education deliberately omitted
    )
    out = str(tmp_path / "w.docx")
    format_compact(r, out)
    text = _docx_text(out)
    assert "TECHNICAL SKILLS" in text and "EDUCATION" in text   # nothing dropped


def test_default_order_unchanged_when_no_section_order():
    order = _resolve_section_order({"additional_sections": [{"heading": "Awards"}]})
    assert order == ["skills", "experience", "projects", "certifications", "additional-0", "education"]


def test_education_keeps_both_institution_and_location(tmp_path):
    r = _base_resume(education=[{"degree": "BS", "institution": "MIT", "location": "Cambridge, MA",
                                 "graduation_date": "2020", "gpa": None, "details": []}])
    out = str(tmp_path / "e.docx")
    format_compact(r, out)
    text = _docx_text(out)
    assert "MIT" in text and "Cambridge, MA" in text
