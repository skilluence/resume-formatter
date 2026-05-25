import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are a resume parser. Extract all information from the resume text and return ONLY valid JSON — no markdown, no explanation.

Return this exact structure:
{
  "name": "string",
  "professional_title": "string or null",
  "contact": {
    "phone": "string or null",
    "email": "string or null",
    "linkedin": "string or null",
    "github": "string or null",
    "location": "string or null"
  },
  "summary": "string or null",
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

Rules:
- Keep all bullet points exactly as written, do not summarize or shorten.
- If a field is missing, use null.
- professional_title: if the resume shows a tagline/title below the name (e.g. "Software Engineer", "Data Scientist"), extract it. Otherwise null.
- skills should group by category if categories exist, otherwise use a single key "General".
- Return ONLY the JSON object, nothing else.
"""


def structure_resume(raw_text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume:\n\n{raw_text}"},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
