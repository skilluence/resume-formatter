"""AI Tailor unit tests.

The OpenAI call is mocked, so these run with no key and no network. They lock in
the core guarantees:
  - the model supplies WORDING; every FACT is re-stamped from the source resume;
  - every experience AND every project is preserved 1:1 (titles/names from source,
    never dropped, never capped, never renamed);
  - bullets are qualitative (no fabricated metrics, no [placeholders]);
  - each experience is capped at 6 bullets and each project carries the full ranked
    `candidate_bullets` set the page-fill engine trims from.
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
        },
        {
            "title": "Office Assistant",
            "company": "Beta LLC",
            "location": "Remote",
            "start_date": "2019",
            "end_date": "2021",
            "bullets": ["Filed paperwork", "Answered phones"],
        },
    ],
    "projects": [
        {"name": "Garden Planner", "tech_stack": "Swift", "bullets": ["Planned gardens"]},
        {"name": "Recipe Box", "tech_stack": "Ruby", "bullets": ["Stored recipes"]},
    ],
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


def _exp(prefix):
    # Six qualitative bullets (no numbers, no [placeholders]) - the new policy.
    return {"bullets": [f"**{prefix}** task {i} delivering clear stakeholder value." for i in range(6)]}


# What a well-behaved model returns: wording only, qualitative, **bold** keywords.
# Note the AI deliberately RENAMES projects and offers its own ordering - the merge
# must override those names with the source names and keep all source projects.
AI_REPLY = {
    "headline": "Senior Data Analyst | BI",
    "summary": "Results-driven analyst with **SQL** and **Tableau** expertise, skilled in **A/B testing** and data storytelling.",
    "skills": {"Languages": ["SQL", "Python"], "BI": ["Tableau", "Power BI"]},
    "experience": [_exp("Built"), _exp("Supported")],
    "projects": [
        {"name": "Churn Model", "tech_stack": "Python, scikit-learn",
         "bullets": ["Built a churn model surfacing at-risk accounts for retention teams.",
                     "Engineered features in **Python** improving signal quality.",
                     "Automated scoring so account managers act sooner.",
                     "Documented the pipeline for repeatable runs."]},
        {"name": "Sales BI", "tech_stack": "Tableau",
         "bullets": ["Designed **Tableau** dashboards consolidating regional sales.",
                     "Modeled metrics so leaders compare performance at a glance.",
                     "Cut manual reporting effort for the team.",
                     "Rolled the views out across departments."]},
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
        "Strengthened every experience to six focused bullets",
        "Enriched each project with ranked, JD-aligned bullets",
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


def _all_strings(resume: dict):
    out = [resume.get("summary") or ""]
    for job in resume.get("experience") or []:
        out += job.get("bullets") or []
    for p in resume.get("projects") or []:
        out += p.get("bullets") or []
        out += p.get("candidate_bullets") or []
    for cat in (resume.get("skills") or {}).values():
        out += cat
    return [s for s in out if isinstance(s, str)]


# ── facts re-stamped ────────────────────────────────────────────────────────
def test_facts_are_preserved_verbatim():
    out = _run_with_reply(AI_REPLY)
    r = out["tailored_resume"]
    assert r["name"] == "Jane Doe"
    assert r["contact"]["email"] == "jane@example.com"
    assert r["education"] == SOURCE["education"]
    assert r["certifications"] == SOURCE["certifications"]
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


def test_signatures_restamped_with_real_name():
    out = _run_with_reply(AI_REPLY)
    assert out["cover_letter"]["signature"] == "Jane Doe"
    assert out["email"]["signature"] == "Jane Doe"


def test_em_dashes_scrubbed():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["summary"] = "Analyst—driven—results"
    out = _run_with_reply(reply)
    assert "—" not in out["tailored_resume"]["summary"]


# ── NEW: never drop / never rename experiences ──────────────────────────────
def test_every_experience_preserved_with_source_titles():
    out = _run_with_reply(AI_REPLY)
    exp = out["tailored_resume"]["experience"]
    assert len(exp) == len(SOURCE["experience"])  # 2 in -> 2 out
    assert [e["title"] for e in exp] == ["Analyst", "Office Assistant"]
    assert [e["company"] for e in exp] == ["Acme Corp", "Beta LLC"]


def test_every_experience_capped_at_six_bullets():
    out = _run_with_reply(AI_REPLY)
    for e in out["tailored_resume"]["experience"]:
        assert len(e["bullets"]) == 6  # both roles get 6, not just the most recent


def test_experience_more_than_six_bullets_truncated():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["experience"][0]["bullets"] = [f"Bullet {i}" for i in range(9)]
    out = _run_with_reply(reply)
    assert len(out["tailored_resume"]["experience"][0]["bullets"]) == 6


def test_experience_empty_bullets_fall_back_to_source():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["experience"][1]["bullets"] = []  # model under-delivered for role 2
    out = _run_with_reply(reply)
    # Never wipe a role: it keeps its source bullets instead of going blank.
    assert out["tailored_resume"]["experience"][1]["bullets"] == ["Filed paperwork", "Answered phones"]


def test_extra_ai_experiences_are_ignored():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["experience"].append(_exp("Phantom"))  # 3 from the model, source has 2
    out = _run_with_reply(reply)
    assert len(out["tailored_resume"]["experience"]) == 2


# ── NEW: never drop / never rename / never cap projects ─────────────────────
def test_every_project_preserved_with_source_names():
    out = _run_with_reply(AI_REPLY)
    projects = out["tailored_resume"]["projects"]
    assert len(projects) == len(SOURCE["projects"])  # 2 in -> 2 out
    # Names come from the SOURCE even though the model renamed them.
    assert [p["name"] for p in projects] == ["Garden Planner", "Recipe Box"]


def test_project_tech_stack_and_bullets_taken_from_ai():
    out = _run_with_reply(AI_REPLY)
    p0 = out["tailored_resume"]["projects"][0]
    assert p0["tech_stack"] == "Python, scikit-learn"
    assert p0["bullets"][0].startswith("Built a churn model")


def test_projects_carry_full_ranked_candidate_bullets():
    out = _run_with_reply(AI_REPLY)
    for p in out["tailored_resume"]["projects"]:
        assert "candidate_bullets" in p
        assert p["candidate_bullets"]  # non-empty ranked set for the fill engine
        assert len(p["candidate_bullets"]) <= 6


def test_project_bullets_capped_at_six():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["projects"][0]["bullets"] = [f"Project bullet {i}" for i in range(8)]
    out = _run_with_reply(reply)
    p0 = out["tailored_resume"]["projects"][0]
    assert len(p0["candidate_bullets"]) == 6
    assert len(p0["bullets"]) <= 6


def test_projects_not_capped_at_two():
    # A four-project resume must keep all four (the old "exactly 2" cap is gone).
    src = json.loads(json.dumps(SOURCE))
    src["projects"] = [
        {"name": f"Proj {i}", "tech_stack": "X", "bullets": [f"src bullet {i}"]} for i in range(4)
    ]
    reply = json.loads(json.dumps(AI_REPLY))
    reply["projects"] = [
        {"name": f"AI Name {i}", "tech_stack": "Y", "bullets": [f"ai bullet {i}", "second"]} for i in range(4)
    ]
    merged = _merge_resume(src, reply)
    assert len(merged["projects"]) == 4
    assert [p["name"] for p in merged["projects"]] == ["Proj 0", "Proj 1", "Proj 2", "Proj 3"]


def test_extra_ai_projects_are_ignored():
    reply = json.loads(json.dumps(AI_REPLY))
    reply["projects"] += [{"name": "Invented", "tech_stack": "Z", "bullets": ["nope"]} for _ in range(3)]
    out = _run_with_reply(reply)
    assert len(out["tailored_resume"]["projects"]) == 2  # source had 2


def test_projects_survive_when_ai_omits_them():
    out = _run_with_reply({**AI_REPLY, "projects": []})
    projects = out["tailored_resume"]["projects"]
    assert [p["name"] for p in projects] == ["Garden Planner", "Recipe Box"]
    assert projects[0]["bullets"] == ["Planned gardens"]  # source bullets retained


# ── NEW: qualitative only - no fabricated placeholders leak through ─────────
def test_no_placeholder_brackets_leak():
    out = _run_with_reply(AI_REPLY)
    for s in _all_strings(out["tailored_resume"]):
        assert "[" not in s and "]" not in s, f"placeholder leaked: {s!r}"


# ── existing guarantees still hold ──────────────────────────────────────────
def test_gaps_returned():
    out = _run_with_reply(AI_REPLY)
    assert out["gaps"] and "cloud" in out["gaps"][0].lower()


def test_original_resume_echoed_back():
    out = _run_with_reply(AI_REPLY)
    assert out["original_resume"]["name"] == "Jane Doe"
    assert out["original_resume"]["experience"][0]["bullets"] == ["did stuff"]


def test_match_computed_after_beats_before():
    out = _run_with_reply(AI_REPLY)
    m = out["match"]
    assert m["jd_skills"]
    assert m["score_after"] >= m["score_before"]
    assert "skills" in m and "keywords" in m
    assert "missing_before" in m["skills"] and "added" in m["skills"]


def test_missing_jd_skill_folded_into_real_category_no_junk_groups():
    out = _run_with_reply(AI_REPLY)
    from match import resume_text, contains
    skills = out["tailored_resume"]["skills"]
    text = resume_text(out["tailored_resume"])
    for s in AI_REPLY["jd_skills"]:
        assert contains(s, text), f"{s} missing after coverage"
    assert out["match"]["skills"]["missing_after"] == []
    # Snowflake (absent from the AI's skills) is folded into a REAL category -
    # never the old junk 'Core Skills' / 'Core Competencies' groups.
    assert "Core Skills" not in skills and "Core Competencies" not in skills
    assert any("Snowflake" in items for items in skills.values())


def test_existing_skills_are_never_removed():
    out = _run_with_reply(AI_REPLY)
    flat = [s for items in out["tailored_resume"]["skills"].values() for s in items]
    for s in ["SQL", "Python", "Tableau", "Power BI"]:
        assert s in flat  # every skill the candidate listed survives


def test_merge_skills_restores_categories_the_ai_dropped():
    from llm.tailor import _merge_skills
    source = {"A": ["x1", "x2"], "B": ["y1"], "C": ["z1", "z2"]}
    ai = {"A": ["x1", "x2", "newjd"]}  # AI dropped categories B and C entirely
    merged = _merge_skills(source, ai)
    flat = {s for items in merged.values() for s in items}
    assert {"x1", "x2", "y1", "z1", "z2", "newjd"} <= flat  # nothing lost; new added
    assert "B" in merged and "C" in merged  # whole dropped categories restored


def test_match_score_is_honest_and_improves():
    out = _run_with_reply(AI_REPLY)
    m = out["match"]
    assert m["score_after"] >= m["score_before"]  # tailoring helps, honestly


def test_no_core_competencies_keyword_stuffing():
    # Even when many JD keywords are missing, we never stuff a junk group to game
    # the score.
    reply = json.loads(json.dumps(AI_REPLY))
    reply["summary"] = "Analyst skilled in **SQL** and **Tableau**."
    reply["jd_keywords"] = ["A/B testing", "data storytelling", "experimentation", "stakeholder management"]
    out = _run_with_reply(reply)
    skills = out["tailored_resume"]["skills"]
    assert "Core Competencies" not in skills and "Core Skills" not in skills


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
    # Projects survive untouched (with source names) even when the AI sends nothing.
    assert [p["name"] for p in merged["projects"]] == ["Garden Planner", "Recipe Box"]
