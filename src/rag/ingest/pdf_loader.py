"""PDF-Loader: Extrahiert Text aus PDF-Dateien.

Verantwortung:
- PDF-Dateien aus data/raw/ lesen
- Rohtext pro Seite extrahieren
- Ergebnis als Liste von Dokumenten zurückgeben
"""

import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def load_pdfs(input_dir: Path) -> list[dict]:
    """Liest alle PDFs aus *input_dir* und gibt pro Seite ein Dokument zurück.

    Jedes Dokument ist ein dict mit ``text`` und ``metadata``
    (source, doc_id, page, filename).
    """
    logger.info("PDF-Loader gestartet für %s", input_dir)
    documents: list[dict] = []

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("Keine PDF-Dateien in %s gefunden", input_dir)
        return documents

    for pdf_path in pdf_files:
        logger.info("Lese PDF: %s", pdf_path.name)
        reader = PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            documents.append({
                "text": text,
                "metadata": {
                    "source": str(pdf_path),
                    "doc_id": f"{pdf_path.stem}_p{page_num}",
                    "page": page_num,
                    "filename": pdf_path.name,
                },
            })

    logger.info(
        "%d Seiten aus %d PDFs extrahiert", len(documents), len(pdf_files)
    )
    return documents
