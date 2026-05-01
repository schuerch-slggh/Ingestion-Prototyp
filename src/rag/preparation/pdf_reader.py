"""Generisches PDF-Lese-Modul auf Basis von PyMuPDF.

Wird von handbuecher.py, modulbeschreibungen.py und schulungsunterlagen.py
wiederverwendet.
"""

import io
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Bilder kleiner als MIN_IMAGE_SIZE x MIN_IMAGE_SIZE Pixel werden verworfen
# (Logos, Trennlinien, winzige UI-Elemente)
MIN_IMAGE_SIZE: int = 50

# Gemeinsame Boilerplate-Pattern für alle PDF-Quellen (zeilenweise geprüft).
# Wiederverwendet von handbuecher.py und modulbeschreibungen.py.
BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\d+$"),                        # isolierte Seitenzahlen
    re.compile(r"^Copyright\s+©", re.IGNORECASE), # Copyright-Zeilen
    re.compile(r"^©\s*\d{4}", re.IGNORECASE),    # © YYYY …
    re.compile(r"^Seite\s+\d+", re.IGNORECASE),  # Seite X / Seite X von Y
]

_RE_MULTI_SPACE = re.compile(r"[ \t]+")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")


def remove_boilerplate(text: str) -> str:
    """Entfernt Boilerplate-Zeilen aus PDF-extrahiertem Text.

    Filtert isolierte Seitenzahlen, Copyright- und Seiten-Marker anhand
    von BOILERPLATE_PATTERNS. Wird von handbuecher.py und
    modulbeschreibungen.py gemeinsam genutzt.
    """
    lines = text.splitlines()
    cleaned = [
        line
        for line in lines
        if not any(pat.match(line.strip()) for pat in BOILERPLATE_PATTERNS)
    ]
    return "\n".join(cleaned).strip()


def _derive_doc_id(pdf_path: Path) -> str:
    """Leitet eine eindeutige doc_id aus dem Dateinamen ab."""
    stem = pdf_path.stem
    return re.sub(r"[^a-zA-Z0-9]+", "_", stem).lower().strip("_")


def _normalize_text(text: str) -> str:
    """Normalisiert Whitespace im extrahierten Text."""
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def read_pdf_text(pdf_path: Path) -> dict:
    """Liest Text und Outline aus einer PDF-Datei.

    Args:
        pdf_path: Pfad zur PDF-Datei.

    Returns:
        Dict mit den Schlüsseln:
        - doc_id (str): aus Dateiname abgeleitet
        - filename (str): Dateiname
        - page_count (int): Seitenanzahl
        - full_text (str): gesamter bereinigter Text
        - pages (list[dict]): pro Seite {"page_number": int, "text": str}
        - outline (list[dict]): {"level": int, "title": str, "page": int}
    """
    doc_id = _derive_doc_id(pdf_path)
    doc = fitz.open(str(pdf_path))
    try:
        toc = doc.get_toc()
        outline = [
            {"level": entry[0], "title": entry[1], "page": entry[2]}
            for entry in toc
        ]

        pages = []
        page_texts = []
        for i, page in enumerate(doc):
            text = _normalize_text(page.get_text())
            pages.append({"page_number": i + 1, "text": text})
            if text:
                page_texts.append(text)

        full_text = _normalize_text("\n\n".join(page_texts))

        logger.info(
            "PDF gelesen: %s (%d Seiten, %d Outline-Einträge)",
            pdf_path.name,
            doc.page_count,
            len(outline),
        )
        return {
            "doc_id": doc_id,
            "filename": pdf_path.name,
            "page_count": doc.page_count,
            "full_text": full_text,
            "pages": pages,
            "outline": outline,
        }
    finally:
        doc.close()


def extract_images(
    pdf_path: Path, output_dir: Path, doc_id: str
) -> list[dict]:
    """Extrahiert eingebettete Bilder aus einer PDF-Datei als PNG.

    Bilder unter MIN_IMAGE_SIZE x MIN_IMAGE_SIZE Pixel werden verworfen.
    Jedes einzigartige Bild (per xref) wird nur einmal extrahiert.

    Args:
        pdf_path: Pfad zur PDF-Datei.
        output_dir: Basisverzeichnis; Bilder landen in output_dir/doc_id/.
        doc_id: Unterverzeichnis-Name.

    Returns:
        Liste von Bild-Metadaten:
        [{"image_id", "page", "filepath", "width", "height"}, ...]
        filepath ist der absolute Pfad zur gespeicherten PNG-Datei.
    """
    try:
        from PIL import Image as PilImage  # noqa: PLC0415
    except ImportError:
        PilImage = None  # type: ignore[assignment]

    img_dir = output_dir / doc_id
    img_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    image_records: list[dict] = []
    seen_xrefs: set[int] = set()
    img_counter = 0
    skipped_small = 0

    try:
        for page_num, page in enumerate(doc, start=1):
            for img_tuple in page.get_images():
                xref = img_tuple[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    img_data = doc.extract_image(xref)
                except Exception:
                    continue

                width = img_data["width"]
                height = img_data["height"]

                if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                    skipped_small += 1
                    continue

                img_counter += 1
                image_id = f"img_{img_counter:03d}"
                img_path = img_dir / f"{image_id}.png"

                raw_bytes = img_data["image"]
                if img_data["ext"] == "png":
                    img_path.write_bytes(raw_bytes)
                elif PilImage is not None:
                    pil_img = PilImage.open(io.BytesIO(raw_bytes))
                    pil_img.save(img_path, format="PNG")
                else:
                    img_path.write_bytes(raw_bytes)

                image_records.append({
                    "image_id": image_id,
                    "page": page_num,
                    "filepath": str(img_path),
                    "width": width,
                    "height": height,
                })
    finally:
        doc.close()

    logger.info(
        "Bilder extrahiert: %d aus %s (verworfen zu klein: %d)",
        img_counter,
        pdf_path.name,
        skipped_small,
    )
    return image_records


def read_pdf(pdf_path: Path, image_output_dir: Path) -> dict:
    """Liest Text, Outline und Bilder aus einer PDF-Datei.

    Kombiniert read_pdf_text() und extract_images().

    Args:
        pdf_path: Pfad zur PDF-Datei.
        image_output_dir: Basisverzeichnis für extrahierte Bilder.

    Returns:
        Dict mit doc_id, filename, page_count, full_text, pages, outline, images.
    """
    doc_id = _derive_doc_id(pdf_path)
    result = read_pdf_text(pdf_path)
    result["images"] = extract_images(pdf_path, image_output_dir, doc_id)
    return result
