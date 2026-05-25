from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
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
    format_type: str = Form("compact"),
):
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

    from ai.structurer import structure_resume
    structured = structure_resume(raw_text)

    candidate_name = structured.get("name", "Unknown")
    job_id, output_path = _versioned_path(candidate_name, format_type)

    from formatters.compact_ats import format_compact
    from formatters.readable import format_readable

    if format_type == "compact":
        format_compact(structured, output_path)
    else:
        format_readable(structured, output_path)

    return JSONResponse({
        "job_id": job_id,
        "candidate_name": candidate_name,
        "docx_url": f"/download/{job_id}/docx",
        "pdf_url": f"/download/{job_id}/pdf",
    })


class BuilderEducation(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None  # "India" or "USA"
    graduation_date: Optional[str] = None


class BuilderExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets_raw: Optional[str] = None  # one bullet per line


class BuilderCertification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None


class BuilderProject(BaseModel):
    name: Optional[str] = None
    tech_stack: Optional[str] = None
    bullets_raw: Optional[str] = None


class BuilderContact(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None


class BuilderRequest(BaseModel):
    contact: BuilderContact
    domain: str
    summary_raw: Optional[str] = None
    skills_raw: Optional[str] = None  # comma-separated
    education_india: List[BuilderEducation] = []
    education_usa: List[BuilderEducation] = []
    experience_india: List[BuilderExperience] = []
    experience_usa: List[BuilderExperience] = []
    projects: List[BuilderProject] = []
    certifications: List[BuilderCertification] = []


@app.post("/build")
def build_resume(req: BuilderRequest):
    if not req.contact.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    if not req.domain.strip():
        raise HTTPException(status_code=400, detail="Domain is required.")

    from ai.builder import build_resume_from_form, suggest_companies

    form_payload = req.model_dump()
    try:
        structured = build_resume_from_form(form_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI build failed: {str(e)}")

    candidate_name = structured.get("name") or req.contact.name
    job_id, output_path = _versioned_path(candidate_name, "compact")

    from formatters.compact_ats import format_compact
    format_compact(structured, output_path)

    # Collect education cities for job leads
    edu_cities: List[Dict[str, str]] = []
    for edu in req.education_india + req.education_usa:
        if edu.city:
            edu_cities.append({
                "city": edu.city,
                "country": edu.country or ("India" if edu in req.education_india else "USA"),
            })

    leads: List[Dict] = []
    try:
        leads = suggest_companies(req.domain, edu_cities)
    except Exception:
        # Job leads are best-effort; don't fail the whole request
        leads = []

    return JSONResponse({
        "job_id": job_id,
        "candidate_name": candidate_name,
        "docx_url": f"/download/{job_id}/docx",
        "pdf_url": f"/download/{job_id}/pdf",
        "job_leads": leads,
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
