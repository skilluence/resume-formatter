"""Robust /tailor resume extraction tests.

The OpenAI call is mocked, so these run with no key and no network. They lock in
the guarantees that make extraction safe to trust over the brittle rule parser:
  - the model's output is normalized to the exact structurer shape;
  - a fact the model INVENTS (not in the source) is dropped (no hallucinated jobs);
  - an entry the model DROPS is recovered from the deterministic parser or, failing
    that, no source line is ever lost (filed under Additional Information);
  - any LLM failure falls back to the deterministic parser so /tailor never breaks.
"""
import json
from unittest.mock import patch

from llm.extract import extract_resume, _normalize, _grounded


SOURCE_TEXT = """John Smith
Senior Engineer
john@example.com | 555-1234 | San Francisco, CA

EXPERIENCE
Staff Engineer | Acme Corp | Jan 2020 - Present | Remote
- Built scalable systems handling heavy traffic
- Led a team of five engineers

Software Engineer | Beta Inc | Jun 2017 - Dec 2019
- Developed REST APIs in Python
- Improved automated test coverage

CERTIFICATIONS
AWS Certified Solutions Architect | Google Cloud Professional | Certified Scrum Master

EDUCATION
B.S. Computer Science | MIT | 2017
"""


def _job(title, company, start, end, bullets, location=None):
    return {"title": title, "company": company, "location": location,
            "start_date": start, "end_date": end, "bullets": bullets}


# A faithful extraction the model would return (verbatim, nothing dropped/merged).
GOOD = {
    "name": "John Smith",
    "headline": "Senior Engineer",
    "contact": {"phone": "555-1234", "email": "john@example.com", "location": "San Francisco, CA"},
    "summary": None,
    "skills": {},
    "experience": [
        _job("Staff Engineer", "Acme Corp", "Jan 2020", "Present",
             ["Built scalable systems handling heavy traffic", "Led a team of five engineers"], "Remote"),
        _job("Software Engineer", "Beta Inc", "Jun 2017", "Dec 2019",
             ["Developed REST APIs in Python", "Improved automated test coverage"]),
    ],
    "projects": [],
    "education": [{"degree": "B.S. Computer Science", "institution": "MIT", "location": None,
                   "graduation_date": "2017", "gpa": None, "details": []}],
    "certifications": [
        {"name": "AWS Certified Solutions Architect", "issuer": None, "date": None, "bullets": []},
        {"name": "Google Cloud Professional", "issuer": None, "date": None, "bullets": []},
        {"name": "Certified Scrum Master", "issuer": None, "date": None, "bullets": []},
    ],
    "additional_sections": [],
}


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _run(reply, text=SOURCE_TEXT):
    with patch("llm.extract.get_client") as gc, patch("llm.extract.get_model", return_value="gpt-4o-mini"):
        gc.return_value.chat.completions.create.return_value = _FakeResp(json.dumps(reply))
        return extract_resume(text)


# ── shape + happy path ──────────────────────────────────────────────────────
def test_normalize_fills_full_structurer_shape():
    r = _normalize({"name": "X"})
    for key in ("name", "headline", "contact", "summary", "skills", "experience",
                "projects", "education", "certifications", "additional_sections"):
        assert key in r
    for key in ("phone", "email", "linkedin", "github", "location", "links"):
        assert key in r["contact"]


def test_extract_keeps_both_experiences_with_identity():
    r = _run(GOOD)
    assert [e["company"] for e in r["experience"]] == ["Acme Corp", "Beta Inc"]
    assert [e["title"] for e in r["experience"]] == ["Staff Engineer", "Software Engineer"]


def test_extract_splits_three_certifications():
    r = _run(GOOD)
    names = [c["name"] for c in r["certifications"]]
    assert len(names) == 3
    assert "Google Cloud Professional" in names


# ── grounding: the model cannot invent ──────────────────────────────────────
def test_grounded_helper():
    toks = {"acme", "corp", "engineer"}
    assert _grounded(toks, "Acme Corp")
    assert not _grounded(toks, "Globex Industries")


def test_invented_experience_is_dropped():
    reply = json.loads(json.dumps(GOOD))
    reply["experience"].append(_job("VP Engineering", "Globex Industries", "2010", "2012", ["ran things"]))
    r = _run(reply)
    companies = [e["company"] for e in r["experience"]]
    assert "Globex Industries" not in companies  # not in the source -> dropped
    assert "Acme Corp" in companies and "Beta Inc" in companies


# ── never drop: recover an entry the model omitted ──────────────────────────
def test_dropped_experience_recovered_from_deterministic():
    reply = json.loads(json.dumps(GOOD))
    reply["experience"] = [reply["experience"][0]]  # model returns only Acme, omits Beta
    r = _run(reply)
    companies = " ".join(e["company"] for e in r["experience"])
    assert "Acme" in companies and "Beta" in companies  # Beta recovered


def test_no_source_line_is_ever_lost():
    # A whole line the model forgot to extract must still surface (lossless guard).
    text = SOURCE_TEXT + "\nAWARDS\nWon the internal hackathon two years running\n"
    r = _run(GOOD, text)  # GOOD has no awards section
    blob = json.dumps(r).lower()
    assert "hackathon" in blob  # filed under Additional Information, never lost


# ── resilience: LLM failure falls back to the deterministic parser ──────────
def test_falls_back_to_deterministic_on_llm_error():
    with patch("llm.extract.get_client") as gc, patch("llm.extract.get_model", return_value="gpt-4o-mini"):
        gc.return_value.chat.completions.create.side_effect = RuntimeError("api down")
        r = extract_resume(SOURCE_TEXT)
    assert r["name"]  # deterministic parser still produced a resume
    assert len(r["experience"]) >= 2
