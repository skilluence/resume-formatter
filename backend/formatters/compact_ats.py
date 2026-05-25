from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy


FONT_NAME = "Calibri"
NAME_SIZE = Pt(16)
TITLE_SIZE = Pt(10.5)
BODY_SIZE = Pt(9)
HEADER_SIZE = Pt(9.5)
MARGIN = Inches(0.20)
COBALT_BLUE = RGBColor(0, 71, 171)
TITLE_GREY = RGBColor(80, 80, 80)


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


def _add_title(doc, title: str):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.font.name = FONT_NAME
    run.font.size = TITLE_SIZE
    run.font.color.rgb = TITLE_GREY


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


def _add_contact(doc, contact: dict):
    p = doc.add_paragraph()
    _set_spacing(p, before=0, after=2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    segments = []
    if contact.get("phone"):
        segments.append(("plain", contact["phone"], None))
    if contact.get("email"):
        segments.append(("link", contact["email"], f"mailto:{contact['email']}"))
    if contact.get("linkedin"):
        raw = contact["linkedin"].strip()
        url = raw if raw.startswith("http") else f"https://www.linkedin.com/in/{raw}"
        segments.append(("link", raw, url))
    if contact.get("github"):
        raw = contact["github"].strip()
        url = raw if raw.startswith("http") else f"https://github.com/{raw}"
        segments.append(("link", raw, url))
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
    usable_width = int((8.5 - 0.40) * 1440)  # twips
    tab_stop.set(qn("w:val"), "right")
    tab_stop.set(qn("w:pos"), str(usable_width))
    tabs.append(tab_stop)
    pPr.append(tabs)

    run_date = p.add_run(date_text)
    run_date.bold = True
    run_date.font.name = FONT_NAME
    run_date.font.size = BODY_SIZE


def _add_bullet(doc, text: str):
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


def format_compact(data: dict, output_path: str):
    doc = Document()
    _set_margins(doc)

    # Remove default paragraph spacing globally
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE

    # Name
    _add_name(doc, data.get("name", ""))

    # Professional title (under name)
    if data.get("professional_title"):
        _add_title(doc, data["professional_title"])

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

    # Education
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
            usable_width = int((8.5 - 0.40) * 1440)
            tab_stop.set(qn("w:val"), "right")
            tab_stop.set(qn("w:pos"), str(usable_width))
            tabs.append(tab_stop)
            pPr.append(tabs)

            if edu.get("graduation_date"):
                run_date = p.add_run(edu["graduation_date"])
                run_date.bold = True
                run_date.font.name = FONT_NAME
                run_date.font.size = BODY_SIZE

            p2 = doc.add_paragraph()
            _set_spacing(p2, before=0, after=1)
            run_inst = p2.add_run(edu.get("institution", ""))
            run_inst.font.name = FONT_NAME
            run_inst.font.size = BODY_SIZE

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
                usable_width = int((8.5 - 0.40) * 1440)
                tab_stop.set(qn("w:val"), "right")
                tab_stop.set(qn("w:pos"), str(usable_width))
                tabs.append(tab_stop)
                pPr.append(tabs)
                run_date = p.add_run(cert["date"])
                run_date.font.name = FONT_NAME
                run_date.font.size = BODY_SIZE

    doc.save(output_path)
    print(f"Saved: {output_path}")
