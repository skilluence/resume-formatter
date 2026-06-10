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
    "summary": "Results-driven analyst with **SQL** and **Tableau** expertise, skilled in **A/B testing** and data storytelling.",
    "skills": {"Languages": ["SQL", "Python"], "BI": ["Tableau", "Power BI"]},
    "experience": [
        {"bullets": [f"**Built** dashboard number {i} improving speed by {20 + i}%." for i in range(6)]}
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
    "jd_skills": ["SQL", "Python", "Tableau", "Power BI", "Snowflake"],
    "jd_keywords": ["A/B testing", "data storytelling"],
    "changes": [
        "Aligned the title and summary to the role",
        "Added the JD's core skills and tools",
        "Rewrote 6 experience bullets with metrics",
        "Added 2 JD-relevant projects",
    ],
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


def test_concrete_numbers_no_placeholders():
    out = _run_with_reply(AI_REPLY)
    joined = " ".join(out["tailored_resume"]["experience"][0]["bullets"])
    assert "[X%]" not in joined and "[" not in joined
    assert "%" in joined  # concrete metric present


def test_gaps_returned():
    out = _run_with_reply(AI_REPLY)
    assert out["gaps"] and "cloud" in out["gaps"][0].lower()


def test_original_resume_echoed_back():
    out = _run_with_reply(AI_REPLY)
    assert out["original_resume"]["name"] == "Jane Doe"
    # The source experience bullet is preserved on the original, not the tailored one.
    assert out["original_resume"]["experience"][0]["bullets"] == ["did stuff"]


def test_match_computed_after_beats_before():
    out = _run_with_reply(AI_REPLY)
    m = out["match"]
    assert m["jd_skills"]
    assert m["score_after"] >= m["score_before"]
    assert "skills" in m and "keywords" in m
    assert "missing_before" in m["skills"] and "added" in m["skills"]


def test_coverage_guarantee_adds_all_jd_skills():
    out = _run_with_reply(AI_REPLY)
    from match import resume_text, contains
    text = resume_text(out["tailored_resume"])
    # Every JD hard skill must be present after the coverage guarantee...
    for s in AI_REPLY["jd_skills"]:
        assert contains(s, text), f"{s} missing after coverage guarantee"
    assert out["match"]["skills"]["missing_after"] == []
    # Snowflake (not in the AI's skills output) was auto-added under Core Skills.
    assert "Core Skills" in out["tailored_resume"]["skills"]
    assert "Snowflake" in out["tailored_resume"]["skills"]["Core Skills"]


def test_tiered_floor_lifts_sparse_resume_to_at_least_70():
    # SOURCE starts with almost nothing matching -> low before -> floor 72.
    out = _run_with_reply(AI_REPLY)
    assert out["match"]["score_before"] < 30
    assert out["match"]["score_after"] >= 70


def test_keywords_injected_into_core_competencies_when_needed():
    # A reply whose summary/bullets DON'T mention the keywords forces injection.
    reply = json.loads(json.dumps(AI_REPLY))
    reply["summary"] = "Analyst skilled in **SQL** and **Tableau**."  # no A/B testing / storytelling
    reply["jd_keywords"] = ["A/B testing", "data storytelling", "experimentation", "stakeholder management"]
    out = _run_with_reply(reply)
    skills = out["tailored_resume"]["skills"]
    # Floor (72) reached by injecting some keywords into Core Competencies.
    assert out["match"]["score_after"] >= 70
    assert "Core Competencies" in skills


def test_changes_returned():
    out = _run_with_reply(AI_REPLY)
    assert isinstance(out["changes"], list) and 3 <= len(out["changes"]) <= 6
    assert any("summary" in c.lower() for c in out["changes"])


def test_scrub_dashes_helper():
    assert _scrub_dashes({"a": ["x—y"], "b": "p–q"}) == {"a": ["x - y"], "b": "p-q"}


def test_merge_ignores_malformed_ai_fields():
    # Missing/empty AI fields must not wipe source content.
    merged = _merge_resume(SOURCE, {"experience": [], "skills": "notadict"})
    assert merged["skills"] == SOURCE["skills"]
    assert merged["experience"][0]["bullets"] == ["did stuff"]
