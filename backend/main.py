from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
from dotenv import load_dotenv
import logging
import os
import re
import shutil
import tempfile
import uuid

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resume.api")

app = FastAPI(title="Resume Formatter API")

# Comma-separated origins, or "*" for any. Logged at startup so a CORS/"failed to
# fetch" misconfig is visible in the deploy logs.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()] or ["*"]
logger.info("[cors] allowed origins: %s", ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads are parsed then deleted immediately — only a transient scratch dir.
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("_")
    return safe or "Resume"


@app.get("/")
def root():
    """Health check / warm-up ping (the frontend hits this to wake a cold server)."""
    return {"status": "Resume Formatter API is running"}


# ─────────────────────────────── parse / structure ──────────────────────────

@app.post("/format")
async def format_resume(file: UploadFile = File(None), plain_text: str = Form(None)):
    """Parse an uploaded resume (or pasted text) into structured JSON for review.

    No document is written here — the user reviews/edits/approves first, then
    calls /build. Every failure path returns a clear 400 with guidance instead
    of a 500, and pasting text is always available as a fallback."""
    if not file and not plain_text:
        raise HTTPException(status_code=400, detail="Provide a file or paste your resume text.")

    raw_text = ""
    if file:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext == ".doc":
            raise HTTPException(
                status_code=400,
                detail="Old .doc files aren't supported — please save it as .docx or PDF, or paste the text.",
            )
        if ext not in (".pdf", ".docx"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF or DOCX files are supported. You can also paste the text instead.",
            )
        tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}{ext}")
        try:
            with open(tmp_path, "wb") as f:
                f.write(await file.read())
            from parsers.pdf_parser import extract_text_from_pdf
            from parsers.docx_parser import extract_text_from_docx
            try:
                raw_text = (
                    extract_text_from_pdf(tmp_path) if ext == ".pdf"
                    else extract_text_from_docx(tmp_path)
                )
            except Exception:
                logger.exception("[format] failed to parse %s", file.filename)
                raise HTTPException(
                    status_code=400,
                    detail="We couldn't read this file — it may be a scanned image, password-protected, "
                           "or corrupted. Try a text-based PDF/DOCX, or paste the text.",
                )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    else:
        raw_text = plain_text

    if not (raw_text or "").strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be read from this resume — if it's a scanned image, paste the text instead.",
        )

    from structurer import structure_resume
    resume = structure_resume(raw_text)
    return JSONResponse({"candidate_name": resume.get("name") or "Unknown", "resume": resume})


# ─────────────────────────────── build / download ───────────────────────────

class BuildRequest(BaseModel):
    resume: Dict[str, Any]


def _require_named_resume(resume):
    if not isinstance(resume, dict) or not (resume.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="A resume with at least a name is required.")


def _fallback_docx(resume: dict, path: str):
    """Last-resort minimal DOCX: the name plus every field as plain text. Even if
    the rich formatter somehow fails, the user still gets a downloadable file with
    nothing lost."""
    from docx import Document
    doc = Document()
    doc.add_paragraph((resume.get("name") or "Resume").strip())

    def emit(value, label=""):
        if isinstance(value, str):
            if value.strip():
                doc.add_paragraph(f"{label}{value.strip()}")
        elif isinstance(value, dict):
            for k, v in value.items():
                emit(v, f"{k}: " if isinstance(v, str) else "")
        elif isinstance(value, list):
            for v in value:
                emit(v)

    for key in ("headline", "contact", "summary", "skills", "experience",
                "projects", "certifications", "additional_sections", "education"):
        emit(resume.get(key))
    doc.save(path)


def _render_docx(resume: dict, path: str):
    from formatters.compact_ats import format_compact
    try:
        format_compact(resume, path)
    except Exception:
        logger.exception("[build] rich formatter failed; using text fallback")
        _fallback_docx(resume, path)


@app.post("/build")
def build_docx(req: BuildRequest):
    """Render the approved resume JSON and stream the DOCX back in ONE request.

    No disk persistence and no second download request, so there's nothing to
    404 if the server restarts/cold-starts between calls."""
    _require_named_resume(req.resume)
    filename = f"{_safe_filename(req.resume.get('name'))}.docx"
    tmpdir = tempfile.mkdtemp(prefix="resume-")
    try:
        path = os.path.join(tmpdir, filename)
        _render_docx(req.resume, path)
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        logger.exception("[build] could not generate DOCX")
        raise HTTPException(status_code=500, detail=f"Couldn't generate the DOCX: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return Response(
        content=data,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _convert_to_pdf(docx_path: str, pdf_path: str, workdir: str):
    """DOCX → PDF. Windows drives Word via docx2pdf; Linux/Mac use LibreOffice
    headless with an isolated profile (concurrency-safe). Raises on failure."""
    if os.name == "nt":
        import pythoncom
        from docx2pdf import convert
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
        finally:
            pythoncom.CoUninitialize()
        if not os.path.exists(pdf_path):
            raise RuntimeError("docx2pdf produced no PDF")
    else:
        import subprocess
        result = subprocess.run(
            [
                "soffice",
                f"-env:UserInstallation=file://{os.path.join(workdir, 'lo-profile')}",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", os.path.dirname(pdf_path),
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not os.path.exists(pdf_path):
            raise RuntimeError(f"soffice exit={result.returncode}; stderr={result.stderr.strip()[:400]}")


@app.post("/build/pdf")
def build_pdf(req: BuildRequest):
    """Render + convert to PDF and stream it back in one request."""
    _require_named_resume(req.resume)
    safe = _safe_filename(req.resume.get("name"))
    tmpdir = tempfile.mkdtemp(prefix="resume-")
    try:
        docx_path = os.path.join(tmpdir, f"{safe}.docx")
        pdf_path = os.path.join(tmpdir, f"{safe}.pdf")
        _render_docx(req.resume, docx_path)
        try:
            _convert_to_pdf(docx_path, pdf_path, tmpdir)
        except FileNotFoundError:
            logger.exception("[build/pdf] LibreOffice (soffice) not found")
            raise HTTPException(
                status_code=500,
                detail="PDF conversion isn't available on the server right now — the DOCX download works.",
            )
        except Exception as e:
            logger.exception("[build/pdf] conversion failed")
            raise HTTPException(
                status_code=500,
                detail=f"PDF conversion failed ({e}). The DOCX download works.",
            )
        with open(pdf_path, "rb") as f:
            data = f.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'},
    )
