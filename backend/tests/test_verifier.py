"""Tests for the fidelity checker (ai/verifier.py).

These are pure-function tests: no network, no OpenAI, no API key. They assert
the two guarantees the client asked for:
  1. Nothing the model invented (not present in the source) survives.
  2. Nothing real i
  s dropped just because the model reformatted it.
"""

import logging

from ai.verifier import verify_against_source, _normalize, _is_grounded


# --- normalization / grounding primitives -----------------------------------

def test_normalize_flattens_punctuation_and_scheme():
    assert _normalize("mailto:Jane@X.com") == "jane@x.com"
    assert _normalize("https://www.LinkedIn.com/in/Jane") == "linkedin.com/in/jane"
    # dashes/bullets and commas collapse to spaces
    assert _normalize("• Python,  SQL ") == "python sql"


def test_is_grounded_short_value_requires_all_tokens():
    source = _normalize("Skilled in Python and SQL")
    tokens = set(source.split())
    assert _is_grounded("Python", source, tokens)
    assert not _is_grounded("Rust", source, tokens)


def test_is_grounded_long_value_allows_minor_drift():
    src = _normalize("Led the migration of the billing system to AWS cloud")
    tokens = set(src.split())
    # genuine bullet, lightly reworded -> still grounded (>=80% tokens present)
    assert _is_grounded("Led the migration of the billing system to AWS", src, tokens)
    # fabricated sentence -> fails
    assert not _is_grounded("Reduced costs by 90% using blockchain synergy", src, tokens)


# --- the reported bug: invented certifications -------------------------------

def test_invented_certification_is_removed():
    raw = "John Doe\nSoftware Engineer\nEXPERIENCE\nBuilt things\nEDUCATION\nBS, MIT, 2018"
    structured = {
        "name": "John Doe",
        "certifications": [
            {"name": "AWS Certified Solutions Architect", "issuer": "Amazon", "date": "2022", "bullets": []}
        ],
    }
    out = verify_against_source(structured, raw)
    assert out["certifications"] == []


def test_real_certification_survives_intact():
    raw = (
        "Jane Roe\nCERTIFICATIONS\n"
        "AWS Certified Cloud Practitioner — Amazon Web Services — 2023"
    )
    structured = {
        "name": "Jane Roe",
        "certifications": [
            {
                "name": "AWS Certified Cloud Practitioner",
                "issuer": "Amazon Web Services",
                "date": "2023",
                "bullets": [],
            }
        ],
    }
    out = verify_against_source(structured, raw)
    assert len(out["certifications"]) == 1
    cert = out["certifications"][0]
    assert cert["name"] == "AWS Certified Cloud Practitioner"
    assert cert["issuer"] == "Amazon Web Services"
    assert cert["date"] == "2023"


def test_reworded_date_is_blanked_but_entry_kept():
    raw = "Jane Roe\nCERTIFICATIONS\nGoogle Data Analytics Certificate Jan 2020"
    structured = {
        "name": "Jane Roe",
        "certifications": [
            {"name": "Google Data Analytics Certificate", "issuer": None,
             "date": "January 2020", "bullets": []}
        ],
    }
    out = verify_against_source(structured, raw)
    assert len(out["certifications"]) == 1
    # "january" isn't in the source ("jan" is) -> date blanked, entry preserved.
    assert out["certifications"][0]["date"] == ""
    assert out["certifications"][0]["name"] == "Google Data Analytics Certificate"


# --- skills: comma-split & hyphenated names are legitimate -------------------

def test_comma_split_skills_survive_and_fabricated_one_dropped():
    raw = "Jane\nSkills: Python, SQL, Java, Power BI"
    structured = {"name": "Jane", "skills": {"Skills": ["Python", "SQL", "Java", "Power BI", "Rust"]}}
    out = verify_against_source(structured, raw)
    assert out["skills"]["Skills"] == ["Python", "SQL", "Java", "Power BI"]


def test_hyphenated_and_dotted_skills_are_not_dropped():
    raw = "Jane\nTools: INDEX-MATCH, Node.js, Data-Driven Decisions"
    structured = {"name": "Jane", "skills": {"Tools": ["INDEX-MATCH", "Node.js", "Data-Driven Decisions"]}}
    out = verify_against_source(structured, raw)
    assert out["skills"]["Tools"] == ["INDEX-MATCH", "Node.js", "Data-Driven Decisions"]


def test_fully_fabricated_skill_category_is_dropped():
    raw = "Jane\nSkills: Python, SQL"
    structured = {"name": "Jane", "skills": {"Skills": ["Python", "SQL"], "Spoken Languages": ["Klingon"]}}
    out = verify_against_source(structured, raw)
    assert "Skills" in out["skills"]
    assert "Spoken Languages" not in out["skills"]


# --- contact + EMBEDDED LINKS routing ----------------------------------------

def test_embedded_links_are_grounded_and_kept():
    raw = (
        "Jane Roe\nSoftware Engineer\n\nEMBEDDED LINKS:\n"
        "mailto:jane@example.com\n"
        "https://linkedin.com/in/janeroe\n"
        "https://github.com/janeroe\n"
        "https://janeroe.dev"
    )
    structured = {
        "name": "Jane Roe",
        "contact": {
            "email": "jane@example.com",
            "linkedin": "linkedin.com/in/janeroe",
            "github": "github.com/janeroe",
            "links": [{"label": "Portfolio", "url": "https://janeroe.dev"}],
        },
    }
    out = verify_against_source(structured, raw)
    c = out["contact"]
    assert c["email"] == "jane@example.com"
    assert c["linkedin"] == "linkedin.com/in/janeroe"
    assert c["github"] == "github.com/janeroe"
    assert c["links"] == [{"label": "Portfolio", "url": "https://janeroe.dev"}]


def test_fabricated_link_is_dropped():
    raw = "Jane Roe\nEMBEDDED LINKS:\nhttps://linkedin.com/in/janeroe"
    structured = {
        "name": "Jane Roe",
        "contact": {"links": [
            {"label": "LinkedIn", "url": "https://linkedin.com/in/janeroe"},
            {"label": "Twitter", "url": "https://twitter.com/madeup"},
        ]},
    }
    out = verify_against_source(structured, raw)
    assert out["contact"]["links"] == [{"label": "LinkedIn", "url": "https://linkedin.com/in/janeroe"}]


# --- experience: per-bullet filtering & whole-entry rules --------------------

def test_fabricated_bullet_dropped_real_bullet_kept():
    raw = (
        "John Doe\nEXPERIENCE\nSenior Engineer, Acme Corp\n"
        "Led the migration of the billing system to AWS"
    )
    structured = {
        "name": "John Doe",
        "experience": [{
            "title": "Senior Engineer", "company": "Acme Corp", "location": None,
            "start_date": "", "end_date": "",
            "bullets": [
                "Led the migration of the billing system to AWS",
                "Reduced costs by 90% using blockchain synergy",
            ],
        }],
    }
    out = verify_against_source(structured, raw)
    assert len(out["experience"]) == 1
    assert out["experience"][0]["bullets"] == ["Led the migration of the billing system to AWS"]


def test_wholly_fabricated_experience_entry_dropped():
    raw = "John Doe\nEXPERIENCE\nSenior Engineer, Acme Corp\nDid work"
    structured = {
        "name": "John Doe",
        "experience": [
            {"title": "Senior Engineer", "company": "Acme Corp", "location": None,
             "start_date": "", "end_date": "", "bullets": []},
            {"title": "Chief Astronaut", "company": "NASA Mars Division", "location": None,
             "start_date": "", "end_date": "", "bullets": []},
        ],
    }
    out = verify_against_source(structured, raw)
    titles = [j["title"] for j in out["experience"]]
    assert titles == ["Senior Engineer"]


# --- safety nets -------------------------------------------------------------

def test_empty_source_returns_input_unchanged():
    structured = {"name": "X", "certifications": [{"name": "Anything", "bullets": []}]}
    out = verify_against_source(structured, "")
    assert out is structured  # bypassed -> nothing dropped


def test_input_is_not_mutated():
    raw = "Jane\nSkills: Python"
    structured = {"name": "Jane", "skills": {"Skills": ["Python", "Rust"]}}
    verify_against_source(structured, raw)
    # original still has the fabricated skill; only the returned copy is cleaned
    assert structured["skills"]["Skills"] == ["Python", "Rust"]


def test_name_never_dropped_but_warns(caplog):
    raw = "A resume body describing duties and projects, with no candidate name line."
    structured = {"name": "Zzqq Wxyz"}
    with caplog.at_level(logging.WARNING, logger="resume.verifier"):
        out = verify_against_source(structured, raw)
    assert out["name"] == "Zzqq Wxyz"
    assert any("KEPT unverified name" in r.message for r in caplog.records)
