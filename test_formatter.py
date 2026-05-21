import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from parsers.docx_parser import extract_text_from_docx
from parsers.pdf_parser import extract_text_from_pdf
from ai.structurer import structure_resume
from formatters.compact_ats import format_compact


def _versioned_output_path(name: str, format_type: str) -> str:
    output_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(output_dir, exist_ok=True)
    safe_name = name.strip().replace(" ", "_")
    version = 1
    while True:
        filename = f"{safe_name}_{format_type}_v{version}.docx"
        full_path = os.path.join(output_dir, filename)
        if not os.path.exists(full_path):
            return full_path
        version += 1


def test(path: str):
    ext = os.path.splitext(path)[1].lower()
    print(f"Step 1: Parsing {path}...")
    raw_text = extract_text_from_pdf(path) if ext == ".pdf" else extract_text_from_docx(path)

    print("Step 2: Structuring with OpenAI...")
    structured = structure_resume(raw_text)

    candidate_name = structured.get("name", "Unknown")
    output_path = _versioned_output_path(candidate_name, "compact")

    print("Step 3: Generating compact ATS DOCX...")
    format_compact(structured, output_path)
    print(f"\nDone! Open this file: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_formatter.py <path_to_resume>")
    else:
        test(sys.argv[1])
