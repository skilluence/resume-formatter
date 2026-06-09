# CLAUDE.md

Guidance for AI agents working in this repository.

## Overview

**Resume Formatter** — turns a raw resume (PDF/DOCX upload or pasted text) into a clean, ATS-ready **DOCX** (and optional PDF) **without losing or inventing a word**. Flow: upload/paste → parse text → **rule-based** structurer builds JSON → user reviews/edits each section → render a styled DOCX → download.

> **The `/format` flow is No-AI, no key.** Earlier versions used GPT-4o-mini to structure resumes; that step was replaced with deterministic Python rules so the output can only ever contain words from the source. The core formatter has no network call and needs no key.
>
> **`/tailor` (beta) is a SEPARATE, opt-in AI feature.** It uses OpenAI to rewrite a resume for a job description and draft a cover letter + HR email. It is clearly labeled "AI-drafted", lives in its own page/endpoints, and **never touches the `/format` guarantee.** Even there, facts (name, contact, employers, titles, dates, education, certifications) are re-stamped from the source in `llm/tailor.py` so the model can only reword bullets/summary/skills/projects — it can never alter a fact, and unknown numbers come back as editable `[placeholders]`, never fabricated. Needs `OPENAI_API_KEY` in `backend/.env` (gitignored); optional `OPENAI_MODEL` (default `gpt-4o-mini`) and `FIRECRAWL_API_KEY` (better job-URL scraping).

Monorepo:
- `frontend/` — Next.js 14 (App Router, TypeScript, Tailwind v4). Deployed on **Vercel**.
- `backend/` — FastAPI (Python 3.10+). Deployed on **Render** (Docker).

## Run locally

- **Backend:** `cd backend && uvicorn main:app --reload` (serves on `:8000`). No key required. Optional `ALLOWED_ORIGINS` env var (defaults to `*`) locks down CORS in production.
- **Frontend:** `cd frontend && npm run dev` (serves on `:3000`). Needs `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000`).

## Pipeline

Two phases: parse + structure first (no file written), then build after the user approves.

`backend/main.py` orchestrates:
1. **Parse** — `parsers/pdf_parser.py` (pdfplumber) / `parsers/docx_parser.py` (python-docx) extract raw text.
2. **Structure** — `structurer.py` turns text into a structured dict using deterministic rules (no AI). Handles two known templates (PDF-style and Word-style); every non-empty source line must land somewhere — `_recover_dropped` is the final guard against data loss.
3. **`POST /format`** returns the structured JSON only — no document is written yet.
4. **Review** — the frontend lets the user keep/skip/edit each section against a live A4 preview.
5. **`POST /build`** renders the approved JSON via `formatters/compact_ats.py` (Calibri, 0.2" margins, cobalt-blue headers, A4) into a DOCX. Output names are auto-versioned (`{name}_compact_v{N}.docx`).
6. **Download** — `GET /download/{job_id}/docx`, or `GET /download/{job_id}/pdf` (converts the DOCX on demand).

## Key files

| File | Responsibility |
|------|----------------|
| `backend/main.py` | FastAPI app: `/format`, `/build`, `/download/{id}/{docx,pdf}`, CORS, versioning |
| `backend/structurer.py` | Rule-based text → structured JSON (no AI, pure stdlib) |
| `backend/formatters/compact_ats.py` | DOCX generation/styling (`format_compact`) |
| `backend/parsers/*.py` | PDF/DOCX text extraction |
| `backend/tests/` | pytest suite (parser, structurer, `/format`→`/build`→`/download` API) |
| `frontend/app/page.tsx` | Landing page (`/`) |
| `frontend/app/format/page.tsx` | Workspace (`/format`) — upload → review |
| `frontend/components/Workspace.tsx` | Two-pane shell (fixed left rail · scrollable preview) |
| `frontend/components/ResumePreview.tsx` | Live paginated A4 document (matches the DOCX) |
| `frontend/components/SectionCard.tsx` | Per-section keep / skip / edit |
| `frontend/lib/` | Resume types, design tokens, helpers |

### AI Tailor (beta) — files

| File | Responsibility |
|------|----------------|
| `backend/llm/client.py` | OpenAI client + model from env (`OPENAI_API_KEY`, `OPENAI_MODEL`) |
| `backend/llm/prompts.py` | Prompt spec (6 exp bullets, 2 projects, ATS skills, 100-word summary, `**bold**`, `[placeholders]`, no em dashes) |
| `backend/llm/tailor.py` | `tailor(resume, jd)` → drafts; **re-stamps facts from source** so the model can't alter them |
| `backend/jd_scraper.py` | `fetch_jd(url)` — httpx+BeautifulSoup, Firecrawl if `FIRECRAWL_API_KEY` set; "" on failure (UI falls back to paste) |
| `backend/formatters/letter.py` | Cover letter + HR email DOCX (letterhead, clickable email/LinkedIn, `**bold**`) |
| `backend/main.py` | `POST /tailor`, `POST /tailor/build`, `GET /tailor/status` |
| `frontend/app/tailor/page.tsx` · `components/TailorWorkspace.tsx` · `components/TailorReview.tsx` · `lib/tailor.ts` | `/tailor` page: input → editable 3-tab review → DOCX/PDF download |

`compact_ats.py` gained `_add_rich_runs` for `**bold**` markup — a **no-op for `/format`** (rule output never contains `**`), so existing DOCX output is byte-identical.

## Gotchas

- `uploads/` and `outputs/` are **local disk** — ephemeral on Render (files vanish on restart). Fine within a single request/response cycle.
- `requirements.txt` lives at **`backend/requirements.txt`**. The `Dockerfile` copies and installs from that path (`pip install -r backend/requirements.txt`), so there's no path mismatch — just keep edits in `backend/requirements.txt`, not the repo root.
- **PDF export needs a converter.** The repo `Dockerfile` installs `libreoffice`/`libreoffice-writer`, and `/download/{job_id}/pdf` converts the DOCX with `soffice --headless` on Linux (and `docx2pdf` + MS Word only on Windows, `os.name == "nt"`). `render.yaml` deploys with `runtime: docker`, so PDF works in the cloud. Do not remove the PDF endpoint, the Dockerfile system deps, or the Docker runtime without removing the PDF buttons too.
- **Never drop or fabricate resume data.** The structurer must preserve every section/line (unrecognised headings included — worst case under an "Additional Information" section), and the rule-based design must never invent content. The frontend `Result` type only uses `job_id` + `candidate_name`.
- `render.yaml` still declares an `OPENAI_API_KEY` env var — it's dead config (nothing reads it) and can be removed.
