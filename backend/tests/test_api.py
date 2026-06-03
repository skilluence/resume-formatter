"""HTTP-level tests for the real API — no browser, fully reproducible.

These hit the actual endpoints through FastAPI's TestClient so you can see
exactly what is being verified:

    cd backend && python -m pytest tests/test_api.py -v

Flow under test:  POST /format  ->  POST /build  ->  GET /download/{id}/docx
plus the GPA-hide path and input validation.
"""

import os
import re
import glob
import copy

import pytest
from fastapi.testclient import TestClient

import main
from parsers.docx_parser import extract_text_from_docx

client = TestClient(main.app)

DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "demoResume")
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
def test_build_then_download_yields_a_real_docx():
    resume = _format_first_pdf().json()["resume"]
    r = client.post("/build", json={"resume": resume})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    dl = client.get(f"/download/{job_id}/docx")
    assert dl.status_code == 200
    assert len(dl.content) > 5000  # a real, non-empty Word document
    assert dl.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml"
    )


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

    job_id = client.post("/build", json={"resume": payload}).json()["job_id"]
    text = extract_text_from_docx(os.path.join(main.OUTPUT_DIR, f"{job_id}.docx"))
    flat = text.replace(" ", "")

    for g in gpa_values:                       # the GPA string is gone
        assert g.replace(" ", "") not in flat
    for e in payload["education"]:             # but the institutions remain
        if e["institution"]:
            assert _toks(e["institution"]).issubset(_toks(text))
