import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


BUILDER_SYSTEM_PROMPT = """You are a professional resume writer. You receive structured form data from a user and produce a polished, ATS-ready resume as JSON.

Return ONLY valid JSON in this exact structure:
{
  "name": "string",
  "headline": "string or null",
  "contact": {
    "phone": "string or null",
    "email": "string or null",
    "linkedin": "string or null",
    "github": "string or null",
    "location": "string or null"
  },
  "summary": "string",
  "skills": {
    "category_name": ["skill1", "skill2"]
  },
  "experience": [
    {
      "title": "string",
      "company": "string",
      "location": "string or null",
      "start_date": "string",
      "end_date": "string",
      "bullets": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "tech_stack": "string or null",
      "bullets": ["string"]
    }
  ],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "graduation_date": "string or null"
    }
  ],
  "certifications": [
    {
      "name": "string",
      "issuer": "string or null",
      "date": "string or null"
    }
  ]
}

Rules — these are strict:

HARD LIMITS — never violate:
- DO NOT invent jobs, companies, employers, titles, or employment dates the user did not list.
- DO NOT fabricate quantitative metrics ("increased X by 30%", "led team of 5", "served 10k users") unless the user wrote that number.
- DO NOT add named technologies, frameworks, or tools to an experience or project that the user did not mention.

EXPANSION — encouraged where the user was vague:
- If a project has only a name and a one-liner (e.g. "Resume Formatter — converts resumes to ATS format"), write 2-3 substantive bullets describing the kind of work that project plausibly entailed at a high level (design, implementation areas, integration, deployment). Stay generic — don't invent specific stacks, percentages, or user counts.
- If an experience entry has only a title/company and a vague one-liner (e.g. "Backend engineer at Acme — worked on APIs"), write 2-3 bullets describing the kind of work that role typically involves, framed in active voice. Do not invent specifics (no metrics, no team sizes, no named systems).
- Polish any bullets the user did write into strong action-verb-led lines. Preserve every factual claim.

OTHER:
- headline: a short professional title derived from the user's domain (e.g. domain "Software Engineering" → "Software Engineer"; "Data Science" → "Data Scientist"). 2-4 words max. Title case.
- contact.linkedin: normalize to a full URL form. If the user gave a handle like "john-doe", output "https://www.linkedin.com/in/john-doe". If they gave a full URL, keep it.
- contact.github: same — normalize handle to "https://github.com/<handle>".
- If summary is empty or weak, write a 2-3 sentence professional summary grounded ONLY in the user's domain, education, real experience, and skills. Never claim years of experience the user didn't state.
- Categorize the skills the user provided into sensible groups (e.g. "Languages", "Frameworks & Libraries", "Tools & Platforms", "Cloud & DevOps", "Databases"). Only include skills the user listed; do not add new ones.
- Combine India and USA education into one array, ordered by graduation_date descending (most recent first). Include the city in the institution string like "MIT, Cambridge, MA".
- Combine India and USA experience into one array, ordered by end_date descending (most recent first; "Present" counts as most recent).
- If a section is empty in the input, return an empty array or null appropriately.
- Return ONLY the JSON object, no markdown fences, no commentary.
"""


def build_resume_from_form(form_data: dict) -> dict:
    """Take structured form input and produce a polished resume JSON."""
    user_payload = json.dumps(form_data, indent=2)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": BUILDER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Build a resume from this form data:\n\n{user_payload}"},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


LEADS_SYSTEM_PROMPT = """You suggest real companies a job-seeker could realistically apply to, based on their domain and the cities where they studied.

Return ONLY valid JSON in this exact structure:
{
  "leads": [
    {
      "company": "string",
      "city": "string",
      "country": "string",
      "why": "one short sentence on why this company fits the user's domain"
    }
  ]
}

Rules:
- Only suggest real, well-known companies that genuinely exist and operate in or near the given city.
- Do NOT invent companies. If you are uncertain a company exists in that city, omit it.
- Mix large employers and notable mid-size firms in the user's domain.
- Aim for 6-10 leads total, spread across the user's education cities.
- Do not include job titles, salaries, or fabricated job postings. Just company + city + a one-line "why".
- Return ONLY the JSON object.
"""


def suggest_companies(domain: str, education_cities: list[dict]) -> list[dict]:
    """Return real companies in the user's domain near their education cities.

    education_cities: [{"city": "Boston", "country": "USA"}, ...]
    """
    if not domain or not education_cities:
        return []

    payload = {
        "domain": domain,
        "cities": education_cities,
    }
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": LEADS_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, indent=2)},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return data.get("leads", [])
