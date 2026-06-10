"""Prompt templates for the AI Tailor feature.

A jobright-grade resume tailoring prompt grounded in how real ATS engines
(Workday, Taleo, Lever, iCIMS, Greenhouse) actually score resumes. Hard rules are
enforced here AND re-checked in code: facts are re-stamped from the source in
tailor.py, and `match.py` plus `ensure_skill_coverage` guarantee keyword coverage.
"""
import json

# ── How an ATS scores a resume (the mental model the model must optimize for) ──
ATS_MODEL = """
HOW APPLICANT TRACKING SYSTEMS SCORE A RESUME (optimize for this):
- The dominant factor (40-50% of the score) is WEIGHTED KEYWORD MATCH between the
  job description and the resume. Weights: hard skills and certifications count
  ~2x, tools ~1.5x, soft/process terms ~0.5x. Missing a required hard skill hurts
  the most.
- EXACT WORDING WINS. Many ATS (Workday, Taleo) do literal string matching, so use
  the JD's exact term ("CI/CD" not "continuous integration", "Kubernetes" not
  "container orchestration"). When a term has a common abbreviation, include BOTH
  forms once, e.g. "Search Engine Optimization (SEO)", "Kubernetes (K8s)".
- DEPTH BEATS STUFFING. A keyword should appear in at least TWO of {summary,
  skills, a recent experience bullet}. A skill listed only in the Skills section
  (no bullet evidence) is scored as "shallow" and de-weighted. Aim for each top
  keyword appearing 2-4 times across the resume, never more (stuffing is penalized).
- THE SKILLS SECTION IS THE HIGHEST-WEIGHTED SECTION, and the FIRST entries carry
  the most weight, so JD-critical skills/tools must come FIRST in their category.
- THE SUMMARY is weighted heavily and read first: it must mirror the JD's job
  TITLE and lead with the top 3-5 JD keywords.
- Recent experience is weighted more than old experience, and a keyword paired with
  a measurable outcome ("cut p95 latency 38% with Redis caching") scores higher
  than a bare duty.
"""

# ── The step-by-step method (how to actually do the tailoring) ─────────────────
METHOD = """
TAILORING METHOD - follow in order:
1. Read the JD and extract its requirements: the exact job title, the hard skills
   and tools (these become "jd_skills"), and the methodologies/domain/scope terms
   (these become "jd_keywords").
2. Rewrite the HEADLINE to mirror the JD's job title.
3. Rewrite the SUMMARY (~100 words) to open with the JD title and weave in the top
   JD keywords/skills, plus one quantified proof point.
4. Rebuild the SKILLS section: keep the candidate's real skills, ADD every JD hard
   skill/tool the candidate could plausibly know given their experience, drop noise,
   and ORDER each category so JD-critical skills appear first.
5. Rewrite EXPERIENCE bullets to surface JD skills in real context with metrics.
   The most recent / most relevant role gets EXACTLY 6 bullets (expand realistically
   if the source has fewer); older roles get 2-3. Each bullet ~30 words:
   Action verb + what you did + the JD tool/skill used + a concrete measurable result.
6. Provide EXACTLY 2 projects most relevant to the JD (prefer the candidate's real
   projects; if none, build realistic ones from their skills + the JD), each with
   2-3 bullets (~35 words): tech stack + role + a concrete outcome. Projects must
   support, not overshadow, the work experience.
7. Ensure every important JD skill appears in at least two places (summary, skills,
   and/or a bullet). Write the cover letter, the HR email, and the "changes" bullets.
"""

# ── Inviolable constraints ─────────────────────────────────────────────────────
HARD_RULES = """
HARD RULES (a violation makes the output unusable):
A. NEVER invent or alter facts: employers, job titles, employment dates, degrees,
   schools, certifications, names, or contact details. You only rewrite WORDING and
   surface/emphasize skills. This is keyword optimization, NOT fabricated history.
B. Use SPECIFIC, REALISTIC metrics (%, counts, $, time saved) - e.g. "reduced
   latency by 35%", "managed 60+ microservices". Prefer figures already in the
   source; when absent, choose a believable, conservative value. NEVER output a
   bracketed placeholder like [X%] and never leave a metric blank.
C. NO em dashes (do not use the "-" long-dash character). Use commas, periods, or a
   spaced hyphen " - ".
D. Bold the ATS-critical keywords with **double asterisks** - the JD-matching terms
   only, used sparingly (never whole sentences). Bold in bullets, summary, projects,
   cover letter, and email.
E. Standard, ATS-safe phrasing and section names. No tables/columns implied.
"""

OUTPUT_CONTRACT = """
Return ONE JSON object with EXACTLY these keys (no extra prose):

{
  "headline": "JD-aligned professional title line, e.g. 'Senior Platform Engineer | Cloud-Native Infrastructure'",
  "summary": "~100-word ATS summary opening with the JD title and top keywords, no em dashes",
  "skills": { "Category Name": ["skill1", "skill2", ...], ... },   // JD-critical skills FIRST in each category
  "experience": [ { "bullets": ["bullet 1", "bullet 2", ...] } ],  // same length & order as the source jobs; bullets ONLY
  "projects": [ { "name": "string", "tech_stack": "string", "bullets": ["...", "..."] } ],  // exactly 2
  "cover_letter": { "greeting": "Dear Hiring Manager,", "body_paragraphs": ["...", "...", "..."], "closing": "Sincerely,", "signature": "Candidate Full Name" },
  "email": { "subject": "string", "greeting": "Dear Hiring Manager,", "body_paragraphs": ["...", "..."], "closing": "Best regards,", "signature": "Candidate Full Name" },
  "gaps": ["short note about a genuinely missing/weak area the candidate should address", ...],
  "jd_skills": ["10-20 HARD skills/tools/technologies/certifications from the JD, in the JD's EXACT wording, e.g. 'Kubernetes', 'CI/CD', 'Apache Kafka'", ...],
  "jd_keywords": ["10-15 OTHER important JD terms (methodologies, domain, scope, soft) that are NOT hard skills, e.g. 'distributed systems', 'observability', 'cross-functional'", ...],
  "changes": ["4-5 SHORT 'what changed' bullets in the style of a change log, e.g. 'Aligned the title and summary to the role', 'Added the JD's core skills and tools', 'Rewrote 6 experience bullets with metrics', 'Added 2 JD-relevant projects'. Each under 12 words, concrete, no fluff.", ...]
}

Rules for the arrays:
- "experience" MUST have the SAME LENGTH and SAME ORDER as the source jobs. Item i
  holds the rewritten bullets for source job i. Do NOT add, remove, or reorder jobs,
  and do NOT output any company/title/date/location - only bullets.
- "jd_skills" and "jd_keywords" must NOT overlap. Together they are the JD's keyword
  set used to score the match, so be thorough and use the JD's exact terms.
"""


def build_messages(resume: dict, jd_text: str) -> list:
    """The chat messages for one tailoring call. The source resume is passed as
    JSON so the model can see the real facts it must preserve and reuse."""
    system = (
        "You are a senior US technical recruiter and ATS resume strategist. You "
        "rewrite a candidate's real resume to match a specific job description so it "
        "scores 90%+ on ATS keyword matching while reading like a strong human draft "
        "and staying 100% truthful about the candidate's history.\n"
        + ATS_MODEL + METHOD + HARD_RULES + OUTPUT_CONTRACT
    )
    user = (
        "SOURCE RESUME (JSON - these facts are the truth, preserve them exactly):\n"
        + json.dumps(resume, ensure_ascii=False, indent=2)
        + "\n\nTARGET JOB DESCRIPTION:\n"
        + jd_text.strip()
        + "\n\nTailor the resume to this job and return ONLY the JSON object specified above."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
