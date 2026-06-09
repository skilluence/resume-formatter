"""Windows-only DOCX → PDF via a dedicated MS Word COM instance.

Invoked as a subprocess by ``_convert_to_pdf`` in ``main.py`` so Word runs on a
clean STA main thread (calling it from a FastAPI worker thread raises
0x800706B5, "the interface is unknown"). ``DispatchEx`` spawns a PRIVATE Word
process rather than attaching to whatever instance is already running, so a
stuck/zombie Word left by an earlier session can't poison the conversion.
"""
import sys

import pythoncom
from win32com.client import DispatchEx

WD_FORMAT_PDF = 17  # wdFormatPDF


def convert(src: str, dst: str) -> None:
    pythoncom.CoInitialize()
    word = DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(src, ReadOnly=True)
        try:
            doc.SaveAs(dst, FileFormat=WD_FORMAT_PDF)
        finally:
            doc.Close(False)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
