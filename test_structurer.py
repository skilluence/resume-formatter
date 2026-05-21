import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from parsers.docx_parser import extract_text_from_docx
from parsers.pdf_parser import extract_text_from_pdf
from ai.structurer import structure_resume


def test(path: str):
    ext = os.path.splitext(path)[1].lower()
    print(f"Extracting text from {path}...")

    if ext == ".pdf":
        raw_text = extract_text_from_pdf(path)
    elif ext in (".docx", ".doc"):
        raw_text = extract_text_from_docx(path)
    else:
        print("Unsupported file type.")
        return

    print("Sending to OpenAI for structuring...\n")
    structured = structure_resume(raw_text)
    print(json.dumps(structured, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_structurer.py <path_to_resume>")
    else:
        test(sys.argv[1])
