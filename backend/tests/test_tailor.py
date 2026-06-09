"""AI Tailor unit tests.

The OpenAI call is mocked, so these run with no key and no network. They lock in
the core guarantee: the model supplies wording, but every FACT is re-stamped from
the source resume - the model can never change who the candidate is.
"""
import json
from unittest.mock import patch

from llm.tailor import tailor, _scrub_dashes, _merge_resume


SOURCE = {
    "name": "Jane Doe",
    "headline": "Data Analyst",
    "contact": {
        "phone": "555-1234",
        "email": "jane@example.com",
        "linkedin": "jane-doe",
        "github": None,
        "location": "Austin, TX",
        "links": [],
    },
    "summary": "Old summary.",
    "skills": {"Tools": ["Excel"]},
    "experience": [
        {
            "title": "Analyst",
            "company": "Acme Corp",
            "location": "Austin, TX",
            "start_date": "2021",
            "end_date": "Present",
            "bullets": ["did stuff"],
        }
    ],
    "projects": [],
    "education": [
        {
            "degree": "B.S. Statistics",
            "institution": "UT Austin",
            "location": "Austin, TX",
            "graduation_date": "2020",
            "gpa": "3.8",
            "details": [],
        }
    ],
    "certifications": [{"name": "Tableau Cert", "issuer": "Tableau", "date": "2022", "bullets": []}],
    "additional_sections": [],
}


# What a well-behaved model would return (wording only, no facts, with **bold**).
AI_REPLY = {
    "headline": "Senior Data Analyst | BI",
    "summary": "Results-driven analyst with **SQL** and **Tableau** expertise.",
    "skills": {"Languages": ["SQL", "Python"], "BI": ["Tableau", "Power BI"]},
    "experience": [
        {"bullets": [f"**Built** dashboard number {i} improving speed by [X%]." for i in range(6)]}
    ],
    "projects": [
        {"name": "Churn Model", "tech_stack": "Python, scikit-learn", "bullets": ["Built model with [X%] accuracy.", "Served [N] users."]},
        {"name": "Sales BI", "tech_stack": "Tableau", "bullets": ["Cut reporting time by [X hours].", "Adopted by [N] teams."]},
    ],
    "cover_letter": {
        "greeting": "Dear Hiring Manager,",
        "body_paragraphs": ["I am excited about the **Data Analyst** role."],
        "closing": "Sincerely,",
        "signature": "WRONG NAME FROM MODEL",
    },
    "email": {
        "subject": "Application - Data Analyst",
        "greeting": "Dear Hiring Manager,",
        "body_paragraphs": ["Please find my resume and cover letter attached."],
        "closing": "Best regards,",
        "signature": "WRONG NAME FROM MODEL",
    },
    "gaps": ["No cloud experience listed - add if you have it."],
}


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _run_with_reply(reply: dict):
    with patch("llm.tailor.get_client") as gc, patch("llm.tailor.get_model", return_value="gpt-4o-mini"):
        client = gc.return_value
        client.chat.completions.create.return_value = _FakeResp(json.dumps(reply))
        return tailor(SOURCE, "We need a Data Analyst with SQL and Tableau.")


def test_facts_are_preserved_verbatim():
    out = _run_with_reply(AI_REPLY)
    r = out["tailored_resume"]
    # Identity + factual sections come straight from the source, untouched.
    assert r["name"] == "Jane Doe"
    assert r["contact"]["email"] == "jane@example.com"
    assert r["education"] == SOURCE["education"]
    assert r["certifications"] == SOURCE["certifications"]
    # Job identity preserved; only bullets change.
    assert r["experience"][0]["title"] == "Analyst"
    assert r["experience"][0]["company"] == "Acme Corp"
    assert r["experience"][0]["start_date"] == "2021"


def test_wording_fields_are_tailored():
    out = _run_with_reply(AI_REPLY)
    r = out["tailored_resume"]
    assert r["headline"] == "Senior Data Analyst | BI"
    assert "SQL" in r["summary"]
    assert "BI" in r["skills"]
    assert len(r["experience"][0]["bullets"]) == 6
    assert len(r["projects"]) == 2


def test_signatures_restamped_with_real_name():
    out = _run_with_reply(AI_REPLY)
    assert out["cover_letter"]["signature"] == "Jane Doe"
    assert out["email"]["signature"] == "Jane Doe"


def test_em_dashes_scrubbed():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["summary"] = "Analyst—driven—results"
    out = _run_with_reply(reply)
    assert "—" not in out["tailored_resume"]["summary"]


def test_placeholders_kept_for_unknown_numbers():
    out = _run_with_reply(AI_REPLY)
    joined = " ".join(out["tailored_resume"]["experience"][0]["bullets"])
    assert "[X%]" in joined


def test_gaps_returned():
    out = _run_with_reply(AI_REPLY)
    assert out["gaps"] and "cloud" in out["gaps"][0].lower()


def test_scrub_dashes_helper():
    assert _scrub_dashes({"a": ["x—y"], "b": "p–q"}) == {"a": ["x - y"], "b": "p-q"}


def test_merge_ignores_malformed_ai_fields():
    # Missing/empty AI fields must not wipe source content.
    merged = _merge_resume(SOURCE, {"experience": [], "skills": "notadict"})
    assert merged["skills"] == SOURCE["skills"]
    assert merged["experience"][0]["bullets"] == ["did stuff"]
