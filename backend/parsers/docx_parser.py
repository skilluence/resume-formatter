from docx import Document

# Glyphs that already mark a bullet, so we don't double-prefix one.
_BULLET_GLYPHS = ("•", "·", "‣", "◦", "▪", "●", "-", "*", "–", "—")


def _is_list_paragraph(p) -> bool:
    """True if a paragraph is a bullet/numbered list item.

    Word stores list membership as numbering (``w:numPr``) or a ``List ...``
    paragraph style — neither shows up in ``p.text``. Without this, Word bullets
    extract as plain lines and the structurer can't tell a bullet from a heading
    or a job title. We mark them so PDF ("• …") and DOCX inputs look the same."""
    pPr = p._p.pPr
    if pPr is not None and pPr.numPr is not None:
        return True
    style = (p.style.name or "").lower() if p.style is not None else ""
    return "list" in style


def _extract_hyperlinks(doc) -> list:
    """Collect embedded hyperlink targets (e.g. a LinkedIn URL shown only as the
    clickable word 'LinkedIn'). Paragraph .text omits these, so they would
    otherwise be lost before the resume reaches the parser/AI."""
    links = []
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype:
            target = rel.target_ref
            if target:
                links.append(target)
    # De-duplicate while preserving order.
    return list(dict.fromkeys(links))


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    lines = []
    for p in doc.paragraphs:
        line = p.text.strip()
        if not line:
            continue
        if _is_list_paragraph(p) and not line.startswith(_BULLET_GLYPHS):
            line = "• " + line
        lines.append(line)
    text = "\n".join(lines)

    links = _extract_hyperlinks(doc)
    if links:
        text += "\n\nEMBEDDED LINKS:\n" + "\n".join(links)

    return text
