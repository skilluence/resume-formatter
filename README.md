<div align="center">

# Resume Formatter

### Turn any messy resume into a clean, ATS-ready document **without losing a single word.**

Upload a PDF or DOCX → review every section live → download a polished **DOCX** or **PDF**.

<br/>

![No AI](https://img.shields.io/badge/100%25_Rule--Based-No_AI-38bdf8?style=for-the-badge)
![Lossless](https://img.shields.io/badge/Lossless-Never_adds,_never_drops-0ea5e9?style=for-the-badge)
![ATS Ready](https://img.shields.io/badge/ATS-Optimized-7dd3fc?style=for-the-badge)

<br/>

![Next.js](https://img.shields.io/badge/Next.js_14-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_v4-38BDF8?style=flat-square&logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=flat-square&logo=vercel&logoColor=white)
![Render](https://img.shields.io/badge/Render-Docker-46E3B7?style=flat-square&logo=render&logoColor=white)

</div>

---

## ✨ What It Does

> [!NOTE]
> **No AI. No API keys. No hallucinations.** Earlier versions used GPT-4o-mini to structure resumes — but an LLM can silently *invent* a certification or a date. This version is **fully rule-based and deterministic**, so the output can only ever contain words that were in your original file.

- 📥 **Parses** PDF and DOCX resumes (and pasted plain text)
- 🧠 **Structures** them with deterministic rules — name, contact, summary, skills, experience, projects, education, certifications, and *any* unrecognised section
- 🖊️ **Review screen** — keep / skip / edit each section with a **live, paginated A4 preview** that matches the download exactly
- 🎨 **Generates** a compact, ATS-friendly DOCX — Calibri, tight 0.2″ margins, cobalt-blue section headers
- 📤 **Exports** as **DOCX** or **PDF**
- 🔒 **Lossless guarantee** — every line of the source lands somewhere in the output; nothing is ever fabricated or dropped

---

## How It Works

```
 Upload / Paste          Parse              Structure (rules)         Review & Edit            Build
 ┌────────────┐    ┌────────────────┐    ┌───────────────────┐    ┌─────────────────┐    ┌──────────────┐
 │ PDF · DOCX │ →  │ pdfplumber /   │ →  │ structurer.py     │ →  │ keep / skip /   │ →  │ DOCX  ·  PDF │
 │ · text     │    │ python-docx    │    │ (deterministic)   │    │ edit + preview  │    │  download    │
 └────────────┘    └────────────────┘    └───────────────────┘    └─────────────────┘    └──────────────┘
       POST /format  ───────────────────────────────────►            POST /build  ──────►  GET /download
```

1. **`POST /format`** parses the upload and returns structured **JSON** — no document is written yet.
2. You **review and edit** each section in the two-pane UI (fixed left rail · scrollable live document on the right).
3. **`POST /build`** renders *exactly* what you approved into a DOCX and returns download links.

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|-----------|
| 🖥️ Frontend | Next.js 14 (App Router), TypeScript, Tailwind v4 — deployed on **Vercel** |
| ⚙️ Backend | FastAPI, Python 3.10+ — deployed on **Render** (Docker) |
| 🧠 Structuring | Pure Python rules (standard library) — **no AI, no network** |
| 📄 PDF parsing | `pdfplumber` |
| 📝 DOCX parsing & generation | `python-docx` |
| 🔄 PDF export | LibreOffice (`soffice`) on Linux/Docker · `docx2pdf` + MS Word on Windows |

---

## 📁 Project Structure

```
resumeFormat/
├── backend/
│   ├── main.py                 # FastAPI app: /format, /build, /download/{id}/{docx,pdf}
│   ├── structurer.py           # 🧠 Rule-based resume → structured JSON (no AI)
│   ├── parsers/
│   │   ├── pdf_parser.py        # Extract text from PDF (pdfplumber)
│   │   └── docx_parser.py       # Extract text from DOCX (python-docx)
│   ├── formatters/
│   │   └── compact_ats.py       # Build the styled ATS DOCX
│   ├── tests/                   # pytest suite (32 tests)
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # "/"        landing page
│   │   ├── format/page.tsx      # "/format"  the workspace
│   │   └── globals.css
│   ├── components/
│   │   ├── Workspace.tsx        # Two-pane shell: upload → review
│   │   ├── ResumePreview.tsx    # Live paginated A4 document
│   │   ├── SectionCard.tsx      # Per-section keep / skip / edit
│   │   └── Landing.tsx
│   └── lib/                     # resume types, design tokens, helpers
├── Dockerfile                  # Backend image (installs LibreOffice for PDF)
├── render.yaml                 # Render deploy (Docker runtime)
└── vercel.json                 # Frontend deploy
```

---

## 🚀 Local Setup

### Prerequisites

- 🐍 Python **3.10+**
- 🟢 Node.js **18+**
- 📄 *(PDF export only)* LibreOffice (Linux/Mac) **or** MS Word (Windows)

> [!TIP]
> **No OpenAI key is required.** The backend has no AI dependency.

### 1 — Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**

> Optional `.env` in `backend/` to lock down CORS in production:
> ```bash
> ALLOWED_ORIGINS=https://your-frontend.vercel.app
> ```

### 2 — Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm run dev
```

Frontend runs at **http://localhost:3000**

### 3 — Try it

1. Open **http://localhost:3000** and click **Format your resume**
2. Upload a PDF/DOCX (or paste text) → **Format resume →**
3. Keep / skip / edit each section, watching the live preview
4. Download as **DOCX** or **PDF** 🎉

> [!IMPORTANT]
> **DOCX export works everywhere out of the box.** **PDF export** needs a converter: LibreOffice on Linux/Mac (and in the Docker image), or on Windows `pip install docx2pdf pywin32` with MS Word installed.

---

## 🔌 API Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET`  | `/` | Health check |
| `POST` | `/format` | Parse an uploaded `file` **or** `plain_text` → structured resume **JSON** |
| `POST` | `/build` | Render approved resume JSON → DOCX; returns `docx_url` + `pdf_url` |
| `GET`  | `/download/{job_id}/docx` | Download the generated DOCX |
| `GET`  | `/download/{job_id}/pdf` | Convert (cached) and download the PDF |

---

## 🧪 Testing

The real test suite lives in `backend/tests/` (parser, structurer, and HTTP/API tests):

```bash
cd backend
python -m pytest -q
```

> ✅ **32 tests** cover lossless structuring across multiple resume layouts and the full `/format` → `/build` → `/download` flow.

---

## ☁️ Deployment

| Part | Where | How |
|------|-------|-----|
| 🖥️ Frontend | **Vercel** | Auto-builds from `vercel.json`. Set `NEXT_PUBLIC_API_URL` to your backend URL. |
| ⚙️ Backend | **Render** | `render.yaml` deploys the `Dockerfile` (Docker runtime). The image installs **LibreOffice** so PDF export works in the cloud. Set `ALLOWED_ORIGINS`. |

> [!NOTE]
> `uploads/` and `outputs/` are **ephemeral local disk** — fine for the request/response cycle, but files don't persist across restarts on serverless/Render.

---

## 💙 Design Principles

| Principle | What it means |
|-----------|---------------|
| 🚫 **Never adds data** | Rules can't invent. Nothing appears in your resume that wasn't in the source. |
| 🛟 **Never drops data** | Unrecognised lines are kept verbatim (worst case: under *Additional Information*), so a parsing miss can never silently lose a word. |
| 🎯 **What you see is what you download** | The live A4 preview is rendered from the same structured data as the DOCX. |
| ✋ **You're in control** | Every section is reviewed and editable before anything is built. |

<div align="center">

---

**Reformat without losing a single word.** 🩵

</div>
