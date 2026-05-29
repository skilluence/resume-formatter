import pdfplumber


def _extract_hyperlinks(page) -> list:
    """Collect embedded hyperlink URLs from a PDF page. Links shown only as
    clickable text (e.g. 'LinkedIn') store their real URL as an annotation that
    page.extract_text() drops, so we recover them explicitly."""
    urls = []
    # pdfplumber surfaces link annotations via .hyperlinks (newer) and .annots.
    for source in (getattr(page, "hyperlinks", None) or [], page.annots or []):
        for item in source:
            uri = item.get("uri") or item.get("URI")
            if uri:
                urls.append(uri)
    return urls


def extract_text_from_pdf(file_path: str) -> str:
    text_parts = []
    links = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if page_text:
                text_parts.append(page_text.strip())
            links.extend(_extract_hyperlinks(page))

    text = "\n\n".join(text_parts)

    unique_links = list(dict.fromkeys(l for l in links if l))
    if unique_links:
        text += "\n\nEMBEDDED LINKS:\n" + "\n".join(unique_links)

    return text
