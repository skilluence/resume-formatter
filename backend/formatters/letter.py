"""DOCX renderers for the AI Tailor cover letter and HR email.

Both share a letterhead with the candidate's name and a contact line whose email
and LinkedIn are real, clickable hyperlinks (reusing compact_ats helpers). Body
paragraphs honour **bold** keyword markup via _add_rich_runs. Business-letter
spacing (1" margins, 11pt Calibri) - distinct from the dense resume layout.
"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from formatters.compact_ats import (
    FONT_NAME,
    COBALT_BLUE,
    _add_hyperlink,
    _add_plain_run,
    _add_rich_runs,
    _profile_url,
    _ensure_scheme,
    _set_spacing,
)

LETTER_FONT_SIZE = Pt(11)
NAME_SIZE = Pt(15)
LETTER_MARGIN = Inches(1.0)
LETTER_WIDTH = Inches(8.5)
LETTER_HEIGHT = Inches(11)


def _setup(doc):
    section = doc.sections[0]
    section.page_width = LETTER_WIDTH
    section.page_height = LETTER_HEIGHT
    section.top_margin = LETTER_MARGIN
    section.bottom_margin = LETTER_MARGIN
    section.left_margin = LETTER_MARGIN
    section.right_margin = LETTER_MARGIN
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = LETTER_FONT_SIZE


def _add_letterhead(doc, name: str, contact: dict):
    """Name (bold cobalt) + a centered contact line with clickable email/LinkedIn,
    matching the resume header so the three documents read as one application."""
    contact = contact or {}
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run((name or "").upper())
    run.bold = True
    run.font.name = FONT_NAME
    run.font.size = NAME_SIZE
    run.font.color.rgb = COBALT_BLUE

    def _clean(key):
        return (contact.get(key) or "").strip()

    segments = []
    phone = _clean("phone")
    if phone:
        segments.append(("plain", phone, None))
    email = _clean("email")
    if email:
        addr = email[len("mailto:"):] if email.lower().startswith("mailto:") else email
        href = email if email.lower().startswith("mailto:") else f"mailto:{email}"
        segments.append(("link", _clean("email_label") or addr, href))
    linkedin, linkedin_label = _clean("linkedin"), _clean("linkedin_label")
    if linkedin or linkedin_label:
        url = _profile_url(linkedin, "linkedin.com", "www.linkedin.com/in/") if linkedin else ""
        segments.append(("link", linkedin_label or "LinkedIn", url))
    location = _clean("location")
    if location:
        segments.append(("plain", location, None))

    if segments:
        cp = doc.add_paragraph()
        _set_spacing(cp, before=0, after=10)
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for i, (kind, text, url) in enumerate(segments):
            if i > 0:
                _add_plain_run(cp, "  |  ")
            if kind == "link":
                _add_hyperlink(cp, text, url)
            else:
                _add_plain_run(cp, text)


def _body_paragraph(doc, text: str, after=8):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=after)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_rich_runs(p, text, LETTER_FONT_SIZE)
    return p


def format_cover_letter(data: dict, output_path: str):
    """data: {name, contact, cover_letter:{greeting, body_paragraphs, closing,
    signature}}."""
    doc = Document()
    _setup(doc)
    letter = data.get("cover_letter") or {}
    _add_letterhead(doc, data.get("name", ""), data.get("contact"))

    if letter.get("greeting"):
        _body_paragraph(doc, letter["greeting"], after=8)
    for para in letter.get("body_paragraphs") or []:
        if str(para).strip():
            _body_paragraph(doc, str(para), after=8)
    if letter.get("closing"):
        _body_paragraph(doc, letter["closing"], after=0)
    if letter.get("signature"):
        sp = doc.add_paragraph()
        _set_spacing(sp, before=0, after=0)
        run = sp.add_run(letter["signature"])
        run.bold = True
        run.font.name = FONT_NAME
        run.font.size = LETTER_FONT_SIZE

    doc.save(output_path)


def format_email(data: dict, output_path: str):
    """data: {name, contact, email:{subject, greeting, body_paragraphs, closing,
    signature}}. The subject is rendered as a bold 'Subject:' line at the top."""
    doc = Document()
    _setup(doc)
    email = data.get("email") or {}

    if email.get("subject"):
        sp = doc.add_paragraph()
        _set_spacing(sp, before=0, after=10)
        lbl = sp.add_run("Subject: ")
        lbl.bold = True
        lbl.font.name = FONT_NAME
        lbl.font.size = LETTER_FONT_SIZE
        _add_rich_runs(sp, email["subject"], LETTER_FONT_SIZE)

    if email.get("greeting"):
        _body_paragraph(doc, email["greeting"], after=8)
    for para in email.get("body_paragraphs") or []:
        if str(para).strip():
            _body_paragraph(doc, str(para), after=8)
    if email.get("closing"):
        _body_paragraph(doc, email["closing"], after=0)
    if email.get("signature"):
        sg = doc.add_paragraph()
        _set_spacing(sg, before=0, after=0)
        run = sg.add_run(email["signature"])
        run.bold = True
        run.font.name = FONT_NAME
        run.font.size = LETTER_FONT_SIZE
    # A clickable contact line under the signature mirrors the resume header.
    _add_letterhead_footer(doc, data.get("contact"))

    doc.save(output_path)


def _add_letterhead_footer(doc, contact: dict):
    contact = contact or {}
    email = (contact.get("email") or "").strip()
    linkedin = (contact.get("linkedin") or "").strip()
    if not email and not linkedin:
        return
    p = doc.add_paragraph()
    _set_spacing(p, before=6, after=0)
    first = True
    if email:
        addr = email[len("mailto:"):] if email.lower().startswith("mailto:") else email
        href = email if email.lower().startswith("mailto:") else f"mailto:{email}"
        _add_hyperlink(p, (contact.get("email_label") or addr), href)
        first = False
    if linkedin:
        if not first:
            _add_plain_run(p, "  |  ")
        url = _profile_url(linkedin, "linkedin.com", "www.linkedin.com/in/")
        _add_hyperlink(p, (contact.get("linkedin_label") or "LinkedIn"), url)
