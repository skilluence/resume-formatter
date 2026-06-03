from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
from dotenv import load_dotenv
import os
import uuid
import aiofiles

load_dotenv()

app = FastAPI(title="Resume Formatter API")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _versioned_path(name: str, format_type: str) -> tuple[str, str]:
    """Returns (job_id, full_output_path) with auto-versioning."""
    safe_name = name.strip().replace(" ", "_")
    version = 1
    while True:
        job_id = f"{safe_name}_{format_type}_v{version}"
        path = os.path.join(OUTPUT_DIR, f"{job_id}.docx")
        if not os.path.exists(path):
            return job_id, path
        version += 1


@app.get("/")
def root():
    return {"status": "Resume Formatter API is running"}


@app.post("/format")
async def format_resume(
    file: UploadFile = File(None),
    plain_text: str = Form(None),
):
    """Parse an uploaded resume into structured JSON for the review screen.

    No document is written here — the user reviews/edits/approves first, then
    calls /build to generate the final DOCX from exactly what they approved."""
    if not file and not plain_text:
        raise HTTPException(status_code=400, detail="Provide a file or plain text.")

    raw_text = ""

    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        tmp_id = str(uuid.uuid4())[:8]
        upload_path = os.path.join(UPLOAD_DIR, f"{tmp_id}{ext}")
        async with aiofiles.open(upload_path, "wb") as f:
            await f.write(await file.read())

        from parsers.pdf_parser import extract_text_from_pdf
        from parsers.docx_parser import extract_text_from_docx

        if ext == ".pdf":
            raw_text = extract_text_from_pdf(upload_path)
        elif ext in (".docx", ".doc"):
            raw_text = extract_text_from_docx(upload_path)
        else:
            raise HTTPException(status_code=400, detail="Only PDF or DOCX files are supported.")
    else:
        raw_text = plain_text

    from structurer import structure_resume
    resume = structure_resume(raw_text)

    return JSONResponse({
        "candidate_name": resume.get("name") or "Unknown",
        "resume": resume,
    })


class BuildRequest(BaseModel):
    resume: Dict[str, Any]


@app.post("/build")
def build_resume(req: BuildRequest):
    """Render the user-approved/edited resume JSON into a downloadable DOCX.

    The frontend has already applied the review choices (skipped sections
    removed, GPA hidden if unwanted), so we render exactly what we're given."""
    resume = req.resume
    if not isinstance(resume, dict) or not (resume.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="A resume with at least a name is required.")

    candidate_name = resume.get("name", "Resume")
    job_id, output_path = _versioned_path(candidate_name, "compact")

    from formatters.compact_ats import format_compact
    format_compact(resume, output_path)

    return JSONResponse({
        "job_id": job_id,
        "candidate_name": candidate_name,
        "docx_url": f"/download/{job_id}/docx",
        "pdf_url": f"/download/{job_id}/pdf",
    })


@app.get("/download/{job_id}/docx")
def download_docx(job_id: str):
    path = os.path.join(OUTPUT_DIR, f"{job_id}.docx")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{job_id}.docx",
    )


@app.get("/download/{job_id}/pdf")
def download_pdf(job_id: str):
    docx_path = os.path.join(OUTPUT_DIR, f"{job_id}.docx")
    pdf_path = os.path.join(OUTPUT_DIR, f"{job_id}.pdf")

    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="Source DOCX not found.")

    if not os.path.exists(pdf_path):
        try:
            if os.name == "nt":
                # Windows: use docx2pdf (drives MS Word via COM)
                import pythoncom
                from docx2pdf import convert
                pythoncom.CoInitialize()
                try:
                    convert(docx_path, pdf_path)
                finally:
                    pythoncom.CoUninitialize()
            else:
                # Linux/Mac: call LibreOffice directly. docx2pdf 0.1.x's Linux
                # path is unreliable; soffice with an isolated profile dir is
                # robust and concurrency-safe.
                import subprocess
                import tempfile
                with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
                    result = subprocess.run(
                        [
                            "soffice",
                            f"-env:UserInstallation=file://{profile}",
                            "--headless",
                            "--convert-to", "pdf",
                            "--outdir", OUTPUT_DIR,
                            docx_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                if result.returncode != 0 or not os.path.exists(pdf_path):
                    raise RuntimeError(
                        f"soffice exit={result.returncode}; "
                        f"stdout={result.stdout.strip()[:400]}; "
                        f"stderr={result.stderr.strip()[:400]}"
                    )
        except FileNotFoundError as e:
            # soffice not installed
            print(f"[pdf] LibreOffice not found: {e}", flush=True)
            raise HTTPException(
                status_code=500,
                detail="PDF conversion failed: LibreOffice (soffice) is not installed on the server.",
            )
        except Exception as e:
            print(f"[pdf] conversion failed: {e}", flush=True)
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {str(e)}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{job_id}.pdf",
    )
