import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from parsers.pdf_parser import extract_text_from_pdf
from parsers.docx_parser import extract_text_from_docx

def test_file(path: str):
    ext = os.path.splitext(path)[1].lower()
    print(f"\n--- Parsing: {path} ---\n")

    if ext == ".pdf":
        text = extract_text_from_pdf(path)
    elif ext in (".docx", ".doc"):
        text = extract_text_from_docx(path)
    else:
        print("Unsupported file type. Use .pdf or .docx")
        return

    print(text)
    print(f"\n--- Total characters extracted: {len(text)} ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_parser.py <path_to_resume.pdf or .docx>")
    else:
        test_file(sys.argv[1])
