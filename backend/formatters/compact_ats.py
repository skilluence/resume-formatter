from docx import Document
from docx.shared import Pt, Inches, Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy
import re

# The "List Bullet" style already draws a marker, so strip any leading bullet
# glyph the source carried (incl. Symbol/Wingdings PUA bullets like U+F0B7) to
# avoid double bullets — defence in depth on top of the structurer's stripping.
_LEADING_BULLET_RE = re.compile(
    r"^\s*[•·‣◦▪●∙○■◆➢➤»-]+\s*"
)


FONT_NAME = "Calibri"
NAME_SIZE = Pt(16)
TITLE_SIZE = Pt(10.5)
BODY_SIZE = Pt(9)
HEADER_SIZE = Pt(9.5)
MARGIN = Inches(0.20)
COBALT_BLUE = RGBColor(0, 71, 171)
HEADLINE_GRAY = RGBColor(64, 64, 64)

# A4 page (210 mm wide). Right-align tab stops sit at the page width minus the
# two side margins, expressed in twips (1 inch = 1440 twips).
A4_WIDTH = Mm(210)
A4_HEIGHT = Mm(297)
USABLE_WIDTH_TWIPS = int((210 / 25.4 - 2 * 0.20) * 1440)


def _set_spacing(paragraph, before=0, after=0, line_rule="auto", line=240):
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"), str(after))
    spacing.set(qn("w:lineRule"), line_rule)
    spacing.set(qn("w:line"), str(line))
    existing = pPr.find(qn("w:spacing"))
    if existing is not None:
        pPr.remove(existing)
    pPr.append(spacing)


def _set_margins(doc):
    section = doc.sections[0]
    section.page_width = A4_WIDTH
    section.page_height = A4_HEIGHT
    section.top_margin = MARGIN
    section.bottom_margin = MARGIN
    section.left_margin = MARGIN
    section.right_margin = MARGIN


def _add_name(doc, name: str):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(name.upper())
    run.bold = True
    run.font.name = FONT_NAME
    run.font.size = NAME_SIZE
    run.font.color.rgb = COBALT_BLUE


def _add_headline(doc, headline: str):
    """The professional title line shown directly under the name (e.g.
    'Data Analyst | BI Analyst'). Subordinate to the name: smaller and muted."""
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(headline)
    run.font.name = FONT_NAME
    run.font.size = TITLE_SIZE
    run.font.color.rgb = HEADLINE_GRAY


def _add_hyperlink(paragraph, text: str, url: str):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rStyle = OxmlElement("w:rStyle")
    rStyle.set(qn("w:val"), "Hyperlink")
    rPr.append(rStyle)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0047AB")
    rPr.append(color)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(BODY_SIZE.pt * 2)))
    rPr.append(sz)
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), FONT_NAME)
    rFonts.set(qn("w:hAnsi"), FONT_NAME)
    rPr.append(rFonts)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    hyperlink.append(r)
    paragraph._p.append(hyperlink)


def _add_plain_run(paragraph, text: str):
    run = paragraph.add_run(text)
    run.font.name = FONT_NAME
    run.font.size = BODY_SIZE


def _ensure_scheme(url: str) -> str:
    """Add https:// only when no scheme is present — never doubles it up."""
    url = url.strip()
    if url.lower().startswith(("http://", "https://", "mailto:", "tel:")):
        return url
    return "https://" + url.lstrip("/")


def _profile_url(raw: str, domain: str, handle_prefix: str) -> str:
    """Build a clickable target for a profile that may be a full URL, a bare
    domain path, or just a username/handle. The displayed text stays exactly
    as the user wrote it — this only affects where the hyperlink points."""
    raw = raw.strip()
    low = raw.lower()
    if low.startswith(("http://", "https://", "www.")) or domain in low:
        return _ensure_scheme(raw)
    # Bare username/handle — attach to the canonical profile path.
    return f"https://{handle_prefix}{raw.lstrip('/')}"


def _add_contact(doc, contact: dict):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    segments = []
    if contact.get("phone"):
        segments.append(("plain", contact["phone"], None))
    if contact.get("email"):
        email = contact["email"].strip()
        href = email if email.lower().startswith("mailto:") else f"mailto:{email}"
        display = email[len("mailto:"):] if email.lower().startswith("mailto:") else email
        segments.append(("link", display, href))
    if contact.get("linkedin"):
        raw = contact["linkedin"].strip()
        segments.append(("link", "LinkedIn", _profile_url(raw, "linkedin.com", "www.linkedin.com/in/")))
    if contact.get("github"):
        raw = contact["github"].strip()
        segments.append(("link", "GitHub", _profile_url(raw, "github.com", "github.com/")))
    for link in contact.get("links") or []:
        url = (link.get("url") or "").strip()
        if not url:
            continue
        label = (link.get("label") or "").strip() or url
        segments.append(("link", label, _ensure_scheme(url)))
    if contact.get("location"):
        segments.append(("plain", contact["location"], None))

    for i, (kind, text, url) in enumerate(segments):
        if i > 0:
            _add_plain_run(p, "  |  ")
        if kind == "link":
            _add_hyperlink(p, text, url)
        else:
            _add_plain_run(p, text)


def _add_section_header(doc, title: str):
    p = doc.add_paragraph()
    _set_spacing(p, before=4, after=1)
    run = p.add_run(title.upper())
    run.bold = True
    run.font.name = FONT_NAME
    run.font.size = HEADER_SIZE
    run.font.color.rgb = COBALT_BLUE

    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_job_header(doc, title: str, company: str, location: str, start: str, end: str):
    p = doc.add_paragraph()
    _set_spacing(p, before=2, after=0)

    left_text = f"{title}  |  {company}"
    if location:
        left_text += f"  |  {location}"
    date_text = f"{start} – {end}"

    run_left = p.add_run(left_text)
    run_left.bold = True
    run_left.font.name = FONT_NAME
    run_left.font.size = BODY_SIZE

    # Right-align the date using a tab stop at page width
    tab = OxmlElement("w:tab")
    run_left._r.append(tab)

    pPr = p._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab_stop = OxmlElement("w:tab")
    usable_width = USABLE_WIDTH_TWIPS
    tab_stop.set(qn("w:val"), "right")
    tab_stop.set(qn("w:pos"), str(usable_width))
    tabs.append(tab_stop)
    pPr.append(tabs)

    run_date = p.add_run(date_text)
    run_date.bold = True
    run_date.font.name = FONT_NAME
    run_date.font.size = BODY_SIZE


def _add_bullet(doc, text: str):
    text = _LEADING_BULLET_RE.sub("", text, count=1)
    p = doc.add_paragraph(style="List Bullet")
    _set_spacing(p, before=0, after=1)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = FONT_NAME
    run.font.size = BODY_SIZE

    pPr = p._p.get_or_add_pPr()
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "180")
    ind.set(qn("w:hanging"), "180")
    existing = pPr.find(qn("w:ind"))
    if existing is not None:
        pPr.remove(existing)
    pPr.append(ind)


def _add_skills(doc, skills: dict):
    for category, items in skills.items():
        p = doc.add_paragraph()
        _set_spacing(p, before=0, after=1)
        run_label = p.add_run(f"{category}: ")
        run_label.bold = True
        run_label.font.name = FONT_NAME
        run_label.font.size = BODY_SIZE
        run_items = p.add_run(", ".join(items))
        run_items.font.name = FONT_NAME
        run_items.font.size = BODY_SIZE


def _add_prose(doc, text: str):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=1)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = FONT_NAME
    run.font.size = BODY_SIZE


def _add_inline_items(doc, items: list):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=1)
    run = p.add_run(", ".join(items))
    run.font.name = FONT_NAME
    run.font.size = BODY_SIZE


def _add_additional_sections(doc, sections: list):
    """Render any non-standard resume heading captured by the parser.

    Each section carries a free-form heading plus a `style` chosen by the
    parser so we can format it like the closest standard section:
      - "skills" -> inline comma-joined line (e.g. Languages, Tools)
      - "list"   -> justified bullets
      - "prose"  -> justified paragraph(s)
    Nothing is dropped: unknown/blank styles fall back to whatever content exists.
    """
    for section in sections:
        heading = (section.get("heading") or "").strip()
        if not heading:
            continue

        items = section.get("items") or []
        text = section.get("text")
        style = (section.get("style") or "").strip().lower()

        # Don't emit an empty header if there's genuinely no content.
        if not items and not (text and text.strip()):
            continue

        _add_section_header(doc, heading)

        if style == "prose" and text and text.strip():
            _add_prose(doc, text.strip())
        elif style == "skills" and items:
            _add_inline_items(doc, items)
        elif style == "list" and items:
            for item in items:
                _add_bullet(doc, item)
        else:
            # Fallback so no information is ever lost, even on an odd style.
            if text and text.strip():
                _add_prose(doc, text.strip())
            for item in items:
                _add_bullet(doc, item)


def format_compact(data: dict, output_path: str):
    doc = Document()
    _set_margins(doc)

    # Remove default paragraph spacing globally
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE

    # Name
    _add_name(doc, data.get("name", ""))

    # Headline (professional title line under the name)
    if data.get("headline"):
        _add_headline(doc, data["headline"])

    # Contact
    if data.get("contact"):
        _add_contact(doc, data["contact"])

    # Summary
    if data.get("summary"):
        _add_section_header(doc, "Professional Summary")
        p = doc.add_paragraph()
        _set_spacing(p, before=0, after=1)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(data["summary"])
        run.font.name = FONT_NAME
        run.font.size = BODY_SIZE

    # Skills
    if data.get("skills"):
        _add_section_header(doc, "Technical Skills")
        _add_skills(doc, data["skills"])

    # Experience
    if data.get("experience"):
        _add_section_header(doc, "Professional Experience")
        for job in data["experience"]:
            _add_job_header(
                doc,
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("start_date", ""),
                job.get("end_date", ""),
            )
            for bullet in job.get("bullets", []):
                _add_bullet(doc, bullet)

    # Projects
    if data.get("projects"):
        _add_section_header(doc, "Projects")
        for project in data["projects"]:
            p = doc.add_paragraph()
            _set_spacing(p, before=2, after=0)
            run_name = p.add_run(project.get("name", ""))
            run_name.bold = True
            run_name.font.name = FONT_NAME
            run_name.font.size = BODY_SIZE
            if project.get("tech_stack"):
                run_stack = p.add_run(f"  |  {project['tech_stack']}")
                run_stack.font.name = FONT_NAME
                run_stack.font.size = BODY_SIZE
                run_stack.italic = True
            for bullet in project.get("bullets", []):
                _add_bullet(doc, bullet)

    # Certifications
    if data.get("certifications"):
        _add_section_header(doc, "Certifications")
        for cert in data["certifications"]:
            p = doc.add_paragraph()
            _set_spacing(p, before=1, after=1)
            run_name = p.add_run(cert.get("name", ""))
            run_name.bold = True
            run_name.font.name = FONT_NAME
            run_name.font.size = BODY_SIZE
            if cert.get("issuer"):
                run_issuer = p.add_run(f"  |  {cert['issuer']}")
                run_issuer.font.name = FONT_NAME
                run_issuer.font.size = BODY_SIZE
            if cert.get("date"):
                tab = OxmlElement("w:tab")
                run_name._r.append(tab)
                pPr = p._p.get_or_add_pPr()
                tabs = OxmlElement("w:tabs")
                tab_stop = OxmlElement("w:tab")
                usable_width = USABLE_WIDTH_TWIPS
                tab_stop.set(qn("w:val"), "right")
                tab_stop.set(qn("w:pos"), str(usable_width))
                tabs.append(tab_stop)
                pPr.append(tabs)
                run_date = p.add_run(cert["date"])
                run_date.font.name = FONT_NAME
                run_date.font.size = BODY_SIZE
            for bullet in cert.get("bullets", []):
                _add_bullet(doc, bullet)

    # Additional / non-standard sections (Awards, Languages, Publications, etc.)
    if data.get("additional_sections"):
        _add_additional_sections(doc, data["additional_sections"])

    # Education — always rendered LAST.
    if data.get("education"):
        _add_section_header(doc, "Education")
        for edu in data["education"]:
            p = doc.add_paragraph()
            _set_spacing(p, before=1, after=0)
            run_deg = p.add_run(edu.get("degree", ""))
            run_deg.bold = True
            run_deg.font.name = FONT_NAME
            run_deg.font.size = BODY_SIZE

            tab = OxmlElement("w:tab")
            run_deg._r.append(tab)

            pPr = p._p.get_or_add_pPr()
            tabs = OxmlElement("w:tabs")
            tab_stop = OxmlElement("w:tab")
            usable_width = USABLE_WIDTH_TWIPS
            tab_stop.set(qn("w:val"), "right")
            tab_stop.set(qn("w:pos"), str(usable_width))
            tabs.append(tab_stop)
            pPr.append(tabs)

            if edu.get("graduation_date"):
                run_date = p.add_run(edu["graduation_date"])
                run_date.bold = True
                run_date.font.name = FONT_NAME
                run_date.font.size = BODY_SIZE

            inst_text = edu.get("institution", "")
            if edu.get("location"):
                inst_text = f"{inst_text}  |  {edu['location']}" if inst_text else edu["location"]
            p2 = doc.add_paragraph()
            _set_spacing(p2, before=0, after=1)
            run_inst = p2.add_run(inst_text)
            run_inst.font.name = FONT_NAME
            run_inst.font.size = BODY_SIZE

            # GPA on its own line (kept separate so the UI can hide it on request).
            if edu.get("gpa"):
                pg = doc.add_paragraph()
                _set_spacing(pg, before=0, after=1)
                run_gpa = pg.add_run(edu["gpa"])
                run_gpa.font.name = FONT_NAME
                run_gpa.font.size = BODY_SIZE

            # Coursework / honours / any other extra academic lines.
            for detail in edu.get("details") or []:
                _add_bullet(doc, detail)

    doc.save(output_path)
    print(f"Saved: {output_path}")
