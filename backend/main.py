from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
