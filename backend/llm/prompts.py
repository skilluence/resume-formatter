"""Prompt templates for the AI Tailor feature.

These encode the user's exact spec for each output. Hard rules enforced here AND
re-checked in code (tailor.py): preserve factual data, never fabricate numbers
(use [bracketed] placeholders), no em dashes, mark ATS keywords with **bold**.
"""
import json

# What the model must return. Factual fields (name/contact/education/certs and
# each job's title/company/dates/location) are NOT asked for here — tailor.py
# re-stamps them from the source so the model can never alter a fact.
OUTPUT_CONTRACT = """
Return a single JSON object with EXACTLY these keys:

{
  "headline": "string - a JD-aligned professional title line, e.g. 'Senior Data Analyst | BI & Analytics'",
  "summary": "string - ~100 word ATS professional summary, no em dashes",
  "skills": { "Category Name": ["skill1", "skill2", ...], ... },
  "experience": [
    { "bullets": ["bullet 1", "bullet 2", ...] }
  ],
  "projects": [
    { "name": "string", "tech_stack": "string", "bullets": ["...", "..."] }
  ],
  "cover_letter": {
    "greeting": "Dear Hiring Manager,",
    "body_paragraphs": ["para 1", "para 2", "para 3"],
    "closing": "Sincerely,",
    "signature": "Candidate Full Name"
  },
  "email": {
    "subject": "string",
    "greeting": "Dear Hiring Manager,",
    "body_paragraphs": ["para 1", "para 2"],
    "closing": "Best regards,",
    "signature": "Candidate Full Name"
  },
  "gaps": ["short note about a missing/weak area the candidate should fix", ...]
}

The "experience" array MUST have the SAME LENGTH and SAME ORDER as the source
jobs you are given. Item i holds the rewritten bullets for source job i. Do not
add, remove, or reorder jobs. Do not output any company, title, date, or
location - only the bullets.
"""

RULES = """
ABSOLUTE RULES (a violation makes the output unusable):
1. NEVER invent employers, job titles, dates, degrees, schools, or certifications.
   You only rewrite the WORDING of bullets, the summary, skills, headline, and projects.
2. NEVER invent a specific number, percentage, or metric. If a real figure is not
   present in the source resume, write a clearly editable placeholder in square
   brackets: [X%], [N users], [$Y], [N hours]. The candidate fills these in later.
   You MAY reuse exact numbers that already appear in the source resume.
3. NO em dashes (do not use the character). Use commas, periods, or " - " (spaced hyphen).
4. Mark the most ATS-relevant keywords in bullets, summary, cover letter, and email
   by wrapping them in **double asterisks** for bold. Bold sparingly - the few terms
   that match the job description, not whole sentences.
5. ATS-friendly: plain language, standard section names, real keywords from the JD.

PROFESSIONAL EXPERIENCE: The most recent / most relevant role MUST carry EXACTLY 6
bullets - if the source lists fewer, expand it with realistic, JD-relevant
responsibilities for that exact role, marking every metric as a [placeholder]. Older
roles get 2 to 3 bullets. Each bullet ~30 words, pattern:
Action Verb + what you did + tech/tool used + measurable result (with a KPI or [placeholder]).

PROJECTS: ALWAYS return EXACTLY 2 projects most relevant to the job, each with 2 to 3
bullets (~35 words each): tech stack + your role + a real outcome (users, performance, %).
They must showcase skills WITHOUT overshadowing the work experience. Prefer projects
already in the source resume; if the source has none or only one, create realistic
projects from the candidate's real skills and the job description, marking ALL outcomes
as [placeholders]. Never return fewer than 2 projects.

TECHNICAL SKILLS: Act as an expert US ATS recruiter. Group skills into sensible
categories and include the high-value keywords this job and domain screen for, but
only skills consistent with the candidate's real background.

SUMMARY: ~100 words, ATS friendly, first-person-implied (no "I"). In "gaps", list the
missing pieces the candidate should fix to better match this job.

COVER LETTER & EMAIL: Tailored to this specific job and company. Professional, concise,
human - not generic AI filler. Bold the keywords that matter. Email is a short note to
HR saying the resume and cover letter are attached.
"""


def build_messages(resume: dict, jd_text: str) -> list:
    """The chat messages for one tailoring call. The source resume is passed as
    JSON so the model can see the real facts it must preserve and reuse."""
    system = (
        "You are an elite US technical recruiter and resume writer who tailors "
        "resumes to a specific job description so they pass ATS screening and read "
        "like a strong human draft.\n" + RULES + "\n" + OUTPUT_CONTRACT
    )
    user = (
        "SOURCE RESUME (JSON - these facts are the truth, preserve them):\n"
        + json.dumps(resume, ensure_ascii=False, indent=2)
        + "\n\nJOB DESCRIPTION:\n"
        + jd_text.strip()
        + "\n\nReturn ONLY the JSON object described above."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
