import io
import requests

from pypdf import PdfReader


def download_pdf(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    return response.content


def extract_pdf_pages(pdf_bytes: bytes):
    reader = PdfReader(
        io.BytesIO(pdf_bytes)
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):
        text = page.extract_text() or ""

        if text.strip():
            pages.append({
                "page": page_number,
                "text": text.strip()
            })

    return pages