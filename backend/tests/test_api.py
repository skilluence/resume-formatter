"""HTTP-level tests for the real API — no browser, fully reproducible.

These hit the actual endpoints through FastAPI's TestClient so you can see
exactly what is being verified:

    cd backend && python -m pytest tests/test_api.py -v

Flow under test:  POST /format  ->  POST /build  (streams the DOCX back in one
request), plus the GPA-hide path, input validation, and error handling.
"""

import os
import io
import re
import glob
import copy

import pytest
from fastapi.testclient import TestClient

import main
from parsers.docx_parser import extract_text_from_docx

client = TestClient(main.app)


def _docx_text_from_bytes(content: bytes) -> str:
    return extract_text_from_docx(io.BytesIO(content))

DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "DemoResumes")
PDFS = sorted(glob.glob(os.path.join(DEMO, "*.pdf")))


def _toks(s):
    return set(t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split() if t)


def _format_first_pdf():
    with open(PDFS[0], "rb") as f:
        r = client.post("/format", files={"file": ("resume.pdf", f, "application/pdf")})
    return r


# ── validation ───────────────────────────────────────────────────────────────

def test_format_requires_some_input():
    assert client.post("/format").status_code == 400


def test_build_rejects_a_nameless_resume():
    assert client.post("/build", json={"resume": {"name": ""}}).status_code == 400


# ── the happy path ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not PDFS, reason="no demo PDFs present")
def test_format_returns_structured_resume():
    r = _format_first_pdf()
    assert r.status_code == 200
    body = r.json()
    assert body["candidate_name"]
    resume = body["resume"]
    assert resume["name"]
    for key in ("experience", "education", "skills", "additional_sections"):
        assert key in resume


@pytest.mark.skipif(not PDFS, reason="no demo PDFs present")
def test_build_streams_a_real_docx():
    resume = _format_first_pdf().json()["resume"]
    r = client.post("/build", json={"resume": resume})
    assert r.status_code == 200
    assert len(r.content) > 5000  # a real, non-empty Word document, in one request
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml"
    )
    assert "attachment" in r.headers.get("content-disposition", "")


# ── the GPA toggle: hides GPA, keeps everything else ─────────────────────────

@pytest.mark.skipif(not PDFS, reason="no demo PDFs present")
def test_gpa_toggle_off_hides_gpa_but_keeps_the_rest():
    resume = None
    for p in PDFS:
        with open(p, "rb") as f:
            d = client.post("/format", files={"file": ("r.pdf", f, "application/pdf")}).json()["resume"]
        if any(e.get("gpa") for e in d["education"]):
            resume = d
            break
    if resume is None:
        pytest.skip("no demo resume carries a GPA")

    gpa_values = [e["gpa"] for e in resume["education"] if e.get("gpa")]
    payload = copy.deepcopy(resume)
    for e in payload["education"]:
        e["gpa"] = None  # this is exactly what the frontend GPA-off toggle does

    r = client.post("/build", json={"resume": payload})
    assert r.status_code == 200
    text = _docx_text_from_bytes(r.content)
    flat = text.replace(" ", "")

    for g in gpa_values:                       # the GPA string is gone
        assert g.replace(" ", "") not in flat
    for e in payload["education"]:             # but the institutions remain
        if e["institution"]:
            assert _toks(e["institution"]).issubset(_toks(text))


# ── error handling & resilience (visible, no demo files needed) ──────────────

def test_doc_file_is_rejected_with_guidance():
    r = client.post("/format", files={"file": ("old.doc", b"\xd0\xcf\x11\xe0junk", "application/msword")})
    assert r.status_code == 400
    assert ".docx" in r.json()["detail"]


def test_unreadable_pdf_returns_clear_error_not_500():
    r = client.post("/format", files={"file": ("broken.pdf", b"not really a pdf", "application/pdf")})
    assert r.status_code == 400
    assert "couldn't read" in r.json()["detail"].lower()


def test_empty_pasted_text_is_rejected():
    r = client.post("/format", data={"plain_text": "    "})
    assert r.status_code == 400


def test_build_with_malformed_links_still_streams_a_docx():
    resume = {
        "name": "Edge Case", "headline": "QA",
        "contact": {"phone": "  ", "email": "   ", "linkedin": "  ", "github": None,
                    "location": "Remote",
                    "links": [{"label": "Portfolio", "url": ""}, {"label": "", "url": ""}]},
        "summary": None, "skills": {}, "experience": [], "projects": [],
        "education": [], "certifications": [], "additional_sections": [],
    }
    r = client.post("/build", json={"resume": resume})
    assert r.status_code == 200
    assert len(r.content) > 1000
    text = _docx_text_from_bytes(r.content)
    low = text.lower()
    assert "edge case" in low and "portfolio" in low and "remote" in low
    # empty/whitespace fields are dropped — no dangling "  |  " separators
    assert "|  |" not in text


def test_build_respects_section_order():
    resume = {
        "name": "Order Test", "headline": None,
        "contact": {"phone": None, "email": None, "linkedin": None, "github": None, "location": None, "links": []},
        "summary": "Summary line.",
        "skills": {"Lang": ["Python"]},
        "experience": [],
        "projects": [{"name": "Proj", "tech_stack": None, "bullets": ["x"]}],
        "education": [{"degree": "BS", "institution": "MIT", "location": None,
                       "graduation_date": "2020", "gpa": None, "details": []}],
        "certifications": [], "additional_sections": [],
        "section_order": ["education", "projects", "skills"],
    }
    r = client.post("/build", json={"resume": resume})
    assert r.status_code == 200
    text = _docx_text_from_bytes(r.content)
    assert text.find("EDUCATION") < text.find("PROJECTS") < text.find("TECHNICAL SKILLS")
