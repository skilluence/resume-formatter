from docx import Document


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
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)

    links = _extract_hyperlinks(doc)
    if links:
        text += "\n\nEMBEDDED LINKS:\n" + "\n".join(links)

    return text
