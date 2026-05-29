# CLAUDE.md

Guidance for AI agents working in this repository.

## Overview

**Resume Formatter** — an AI app that turns a raw resume (PDF/DOCX upload or pasted text) into a clean, ATS-ready **DOCX**. Flow: upload/paste → parse text → GPT-4o-mini structures it into JSON → render a styled DOCX → download.

Monorepo:
- `frontend/` — Next.js 14 (App Router, TypeScript, Tailwind v4). Deployed on **Vercel**.
- `backend/` — FastAPI (Python 3.10+). Deployed on **Render**.

## Run locally

- **Backend:** `cd backend && uvicorn main:app --reload` (serves on `:8000`). Needs `OPENAI_API_KEY` in `.env`.
- **Frontend:** `cd frontend && npm run dev` (serves on `:3000`). Needs `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000`).

## Pipeline

`backend/main.py` (`POST /format`) orchestrates:
1. **Parse** — `parsers/pdf_parser.py` (pdfplumber) / `parsers/docx_parser.py` (python-docx) extract raw text.
2. **Structure** — `ai/structurer.py` sends text to OpenAI GPT-4o-mini (JSON mode, temperature 0) → structured dict.
3. **Format** — `formatters/compact_ats.py` builds the DOCX (Calibri, 0.2" margins, cobalt-blue headers). `formatters/readable.py` currently just aliases `format_compact`.
4. **Download** — `GET /download/{job_id}/docx` serves the file. Output names are auto-versioned (`{name}_{format}_v{N}.docx`).

## Key files

| File | Responsibility |
|------|----------------|
| `backend/main.py` | FastAPI app, `/format` + `/download/{id}/docx`, CORS, versioning |
| `backend/ai/structurer.py` | OpenAI call + system prompt + JSON schema |
| `backend/formatters/compact_ats.py` | DOCX generation/styling |
| `backend/parsers/*.py` | PDF/DOCX text extraction |
| `frontend/app/page.tsx` | Entire UI (single page): upload/paste, stage state machine, download |
| `frontend/app/globals.css` | Claude-inspired design tokens (Tailwind v4 `@theme`/`@utility`) |

## File ownership (current parallel work — avoid cross-edits)

| Owner | Exclusive files |
|-------|-----------------|
| Issue 1 (fidelity + dynamic sections) | `backend/ai/structurer.py`, `backend/formatters/compact_ats.py` |
| Frontend (loading UI + remove PDF button) | `frontend/app/page.tsx`, `frontend/app/globals.css` |
| Backend (remove PDF endpoint/dep) | `backend/main.py`, `backend/requirements.txt` |

## Gotchas

- `uploads/` and `outputs/` are **local disk** — ephemeral on Render/serverless (files vanish on restart).
- `requirements.txt` lives at **`backend/requirements.txt`**, but `render.yaml` runs `pip install -r requirements.txt` from the repo root — watch this path mismatch.
- **PDF support has been removed — DOCX only.** `docx2pdf` requires Microsoft Word and cannot run on Render's Linux host. Do **not** reintroduce `docx2pdf` or a Word/LibreOffice dependency.
- The frontend `Result` type only uses `job_id` + `candidate_name`; the formatter must never drop or fabricate resume data — preserve every section, including unrecognised headings.
