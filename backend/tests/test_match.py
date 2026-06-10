"""Deterministic weighted JD keyword match scorer + before/after deltas."""
from match import resume_text, contains, compute_match, SKILL_WEIGHT, KEYWORD_WEIGHT


RESUME = {
    "headline": "Data Analyst",
    "summary": "Experienced in SQL and Python.",
    "skills": {"Tools": ["Tableau", "Excel"]},
    "experience": [{"title": "Analyst", "bullets": ["Built **Power BI** dashboards with Airflow."]}],
    "projects": [{"name": "Churn", "tech_stack": "scikit-learn", "bullets": ["Modeled churn."]}],
}


def test_resume_text_flattens_lowercases_strips_markup():
    t = resume_text(RESUME)
    assert "sql" in t and "tableau" in t and "power bi" in t and "airflow" in t
    assert "*" not in t


def test_contains_word_boundary_vs_substring():
    assert contains("SQL", "experienced in sql and python")
    assert not contains("SQL", "postgresql only")
    assert contains("CI/CD", "we use ci/cd pipelines")


def test_weighted_score_skills_count_double():
    # original has none of these; tailored is RESUME.
    original = {"summary": "Knows Excel.", "skills": {}, "experience": [], "projects": []}
    m = compute_match(
        jd_keywords=["observability"],          # weight 1, absent in both
        jd_skills=["SQL", "Python", "Tableau"],  # weight 2 each, present in tailored
        original=original,
        tailored=RESUME,
    )
    # total = 2*3 + 1*1 = 7. after: 3 skills matched (6), 0 keywords -> 6/7 = 86.
    assert m["score_before"] == 0
    assert m["score_after"] == round(6 / 7 * 100)
    assert SKILL_WEIGHT == 2 and KEYWORD_WEIGHT == 1


def test_deltas_added_and_missing():
    original = {"summary": "Knows Excel.", "skills": {}, "experience": [], "projects": []}
    m = compute_match(["observability"], ["SQL", "Python", "Kafka"], original, RESUME)
    # SQL & Python newly present (added); Kafka still missing.
    assert set(m["skills"]["added"]) == {"SQL", "Python"}
    assert m["skills"]["missing_after"] == ["Kafka"]
    assert "observability" in m["keywords"]["missing_after"]


def test_term_in_both_lists_counts_once_as_skill():
    m = compute_match(["SQL"], ["SQL"], RESUME, RESUME)
    # SQL deduped into skills; keywords becomes empty.
    assert m["jd_skills"] == ["SQL"]
    assert m["jd_keywords"] == []
