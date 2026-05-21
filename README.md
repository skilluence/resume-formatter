# Resume Formatter

Transform unformatted resumes into ATS-ready, recruiter-friendly documents using AI.

Upload a PDF or DOCX → AI structures it → Download a beautifully formatted DOCX + PDF.

---

## What It Does

- Parses PDF and DOCX resumes
- Uses OpenAI GPT-4o-mini to extract structured data (name, contact, summary, skills, experience, projects, education, certifications)
- Generates a compact ATS-optimized DOCX with Calibri font, cobalt blue headers, tight margins
- Exports as both DOCX and PDF
- Clean Next.js frontend with drag & drop upload

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.10+ |
| AI | OpenAI GPT-4o-mini |
| PDF Parsing | pdfplumber |
| DOCX Parsing | python-docx |
| DOCX Generation | python-docx |
| PDF Export | docx2pdf (Windows) / LibreOffice (Linux) |

---

## Project Structure

```
resumeFormat/
├── backend/
│   ├── main.py                  # FastAPI app, routes
│   ├── parsers/
│   │   ├── pdf_parser.py        # Extract text from PDF
│   │   └── docx_parser.py       # Extract text from DOCX
│   ├── ai/
│   │   └── structurer.py        # OpenAI → structured JSON
│   └── formatters/
│       ├── compact_ats.py       # Compact ATS DOCX formatter
│       └── readable.py          # Readable format (uses compact)
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Main UI
│   │   └── globals.css
│   ├── package.json
│   └── next.config.js
├── requirements.txt
├── .env                         # Not committed — create manually
└── README.md
```

---

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key
- Microsoft Word (Windows) or LibreOffice (Linux/Mac) — for PDF export

---

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/resume-formatter.git
cd resume-formatter
```

---

### 2. Backend setup

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Create `.env` file in the root:**
```bash
# .env
OPENAI_API_KEY=sk-your-openai-key-here
```

**Run the backend:**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`

---

### 3. Frontend setup

```bash
cd frontend
npm install
```

**Create `.env.local` inside the `frontend/` folder:**
```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Run the frontend:**
```bash
npm run dev
```

Frontend runs at: `http://localhost:3000`

---

### 4. Test it locally

Open `http://localhost:3000` in your browser:
1. Upload a PDF or DOCX resume
2. Click **Start Formatting**
3. Download the result as **DOCX** or **PDF**

---

### Testing individual components

**Test PDF/DOCX parser only:**
```bash
python test_parser.py "path/to/resume.pdf"
python test_parser.py "path/to/resume.docx"
```

**Test OpenAI structurer only:**
```bash
python test_structurer.py "path/to/resume.docx"
```

**Test full formatter (no frontend needed):**
```bash
python test_formatter.py "path/to/resume.docx"
# Output saved to: outputs/CandidateName_compact_v1.docx
```

---