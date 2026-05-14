"""V4 Vorbereitung: Bilder-Analyse für eine Schulungsunterlagen-PDF.

Extrahiert Statistiken zu Bildern in einer PDF-Datei und speichert
eine Stichprobe zur visuellen Inspektion. Keine VLM-Calls.

V4 wird nur auf Bilder >=300 px angewendet (medium/large), kleinere
Bilder werden aus der Stichprobe und der V4-Verarbeitung ausgeschlossen.
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

logger = logging.getLogger(__name__)


# Konfiguration
PDF_PATH = Path(
    "data/bronze/schulungsunterlagen/Schulungsunterlagen Auftrag Einsteiger.pdf"
)
OUTPUT_DIR = Path("data/analysis/v4_images")
SAMPLE_DIR = OUTPUT_DIR / "samples"
REPORT_PATH = OUTPUT_DIR / "image_analysis_report.json"
MARKDOWN_REPORT = OUTPUT_DIR / "image_analysis_report.md"
SAMPLE_SIZE = 15
V4_MIN_PIXEL_THRESHOLD = 300  # Bilder unter diesem Wert werden ausgeschlossen

# Kostenschätzung pro Bild (Stand Mai 2026)
GPT_4O_MINI_COST_PER_IMAGE_MIN = 0.0002
GPT_4O_MINI_COST_PER_IMAGE_MAX = 0.0005
GPT_4O_COST_PER_IMAGE_MIN = 0.002
GPT_4O_COST_PER_IMAGE_MAX = 0.005


def analyze_pdf_images(pdf_path: Path) -> list[dict]:
    """Extrahiert Metadaten zu allen Bildern im PDF."""
    doc = fitz.open(pdf_path)
    images_info: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_idx, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception as exc:
                logger.warning(
                    "Bild auf Seite %d, idx %d konnte nicht extrahiert werden: %s",
                    page_num + 1,
                    img_idx,
                    exc,
                )
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            max_dim = max(width, height)

            images_info.append(
                {
                    "page": page_num + 1,
                    "image_index": img_idx,
                    "xref": xref,
                    "width": width,
                    "height": height,
                    "max_dim": max_dim,
                    "size_bytes": len(base_image["image"]),
                    "format": base_image["ext"],
                    "aspect_ratio": round(width / max(height, 1), 2),
                    "v4_relevant": max_dim >= V4_MIN_PIXEL_THRESHOLD,
                }
            )

    doc.close()
    return images_info


def categorize_by_size(images: list[dict]) -> dict[str, int]:
    """Kategorisiert Bilder nach maximaler Pixel-Dimension."""
    categories: Counter[str] = Counter()
    for img in images:
        max_dim = img["max_dim"]
        if max_dim < 100:
            categories["tiny"] += 1
        elif max_dim < 300:
            categories["small"] += 1
        elif max_dim < 800:
            categories["medium"] += 1
        else:
            categories["large"] += 1
    return dict(categories)


def save_sample_images(
    pdf_path: Path, images: list[dict], sample_dir: Path, n: int
) -> list[dict]:
    """Speichert eine Stichprobe von V4-relevanten Bildern."""
    sample_dir.mkdir(parents=True, exist_ok=True)

    relevant = [img for img in images if img["v4_relevant"]]

    if len(relevant) <= n:
        sampled = relevant
    else:
        step = max(1, len(relevant) // n)
        sampled = relevant[::step][:n]

    doc = fitz.open(pdf_path)
    saved: list[dict] = []

    for img_meta in sampled:
        try:
            base_image = doc.extract_image(img_meta["xref"])
            ext = base_image["ext"]
            filename = (
                f"page{img_meta['page']:03d}_"
                f"img{img_meta['image_index']:02d}_"
                f"{img_meta['width']}x{img_meta['height']}.{ext}"
            )
            out_path = sample_dir / filename
            out_path.write_bytes(base_image["image"])

            saved.append(
                {
                    "page": img_meta["page"],
                    "filename": filename,
                    "size": f"{img_meta['width']}x{img_meta['height']}",
                    "format": ext,
                }
            )
        except Exception as exc:
            logger.warning("Konnte Sample nicht speichern: %s", exc)

    doc.close()
    return saved


def _size_desc(cat: str) -> str:
    return {
        "tiny": "<100 px",
        "small": "100-300 px",
        "medium": "300-800 px",
        "large": ">800 px",
    }.get(cat, "?")


def build_markdown_report(
    pdf_path: Path,
    images: list[dict],
    by_page: dict[int, int],
    size_categories: dict[str, int],
    samples: list[dict],
) -> str:
    """Baut den Markdown-Report mit allen Statistiken."""
    n_images = len(images)
    n_pages_with_images = len(by_page)
    n_v4_relevant = sum(1 for img in images if img["v4_relevant"])
    n_excluded = n_images - n_v4_relevant

    avg_per_page = n_images / max(n_pages_with_images, 1)
    max_per_page = max(by_page.values()) if by_page else 0

    lines = [
        f"# V4 Image Analysis: {pdf_path.name}",
        "",
        "## Übersicht",
        "",
        "| Aspekt | Wert |",
        "| --- | --- |",
        f"| PDF-Datei | `{pdf_path.name}` |",
        f"| Gesamtanzahl Bilder | {n_images} |",
        f"| Davon V4-relevant (>={V4_MIN_PIXEL_THRESHOLD} px) | **{n_v4_relevant}** |",
        f"| Davon ausgeschlossen (<{V4_MIN_PIXEL_THRESHOLD} px) | {n_excluded} |",
        f"| Seiten mit Bildern | {n_pages_with_images} |",
        f"| Bilder pro Seite (Mittelwert) | {avg_per_page:.1f} |",
        f"| Bilder pro Seite (Maximum) | {max_per_page} |",
        "",
        "## Grössenverteilung",
        "",
        "| Kategorie | Pixelbereich | Anzahl | Anteil | V4-relevant |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cat in ["tiny", "small", "medium", "large"]:
        count = size_categories.get(cat, 0)
        pct = 100 * count / max(n_images, 1)
        relevant = "ja" if cat in ("medium", "large") else "nein"
        lines.append(
            f"| {cat} | {_size_desc(cat)} | {count} | {pct:.1f}% | {relevant} |"
        )

    lines.extend(
        [
            "",
            f"## Stichprobe ({len(samples)} V4-relevante Bilder)",
            "",
            f"Gespeichert in: `{SAMPLE_DIR}`",
            "",
            f"Hinweis: Nur Bilder >={V4_MIN_PIXEL_THRESHOLD} px in der Stichprobe.",
            "",
            "| Seite | Datei | Grösse | Format |",
            "| --- | --- | --- | --- |",
        ]
    )
    for s in samples:
        lines.append(
            f"| {s['page']} | `{s['filename']}` | {s['size']} | {s['format']} |"
        )

    lines.extend(
        [
            "",
            "## Kostenschätzung VLM (nur V4-relevante Bilder)",
            "",
            f"Bei {n_v4_relevant} V4-relevanten Bildern:",
            "",
            "| Modell | Pro Bild | Gesamt (Bandbreite) |",
            "| --- | --- | --- |",
            f"| gpt-4o-mini"
            f" | ${GPT_4O_MINI_COST_PER_IMAGE_MIN:.4f}"
            f"-${GPT_4O_MINI_COST_PER_IMAGE_MAX:.4f}"
            f" | ${n_v4_relevant * GPT_4O_MINI_COST_PER_IMAGE_MIN:.2f}"
            f" - ${n_v4_relevant * GPT_4O_MINI_COST_PER_IMAGE_MAX:.2f} |",
            f"| gpt-4o"
            f" | ${GPT_4O_COST_PER_IMAGE_MIN:.4f}"
            f"-${GPT_4O_COST_PER_IMAGE_MAX:.4f}"
            f" | ${n_v4_relevant * GPT_4O_COST_PER_IMAGE_MIN:.2f}"
            f" - ${n_v4_relevant * GPT_4O_COST_PER_IMAGE_MAX:.2f} |",
            "",
            "Annahmen: ~250-500 Input-Tokens pro Bild (low/high detail mode),",
            "~150-300 Output-Tokens pro Bild-Beschreibung.",
            "",
            "## Zeit-Schätzung",
            "",
            f"Bei sequenziellem Aufruf und ~3 Sekunden pro Bild:"
            f" ca. {n_v4_relevant * 3 // 60} Minuten reine API-Zeit.",
            "",
            "## Hinweise zur Stichprobe",
            "",
            "Die Bilder in `samples/` sind durch gleichmässiges Sampling aus",
            f"der Liste der V4-relevanten Bilder (>={V4_MIN_PIXEL_THRESHOLD} px)",
            "ausgewählt. Bilder unter dem Schwellwert sind nicht in der Stichprobe",
            "enthalten, weil sie für V4 nicht verarbeitet werden.",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    if not PDF_PATH.exists():
        print(f"FEHLER: {PDF_PATH} nicht gefunden")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Analysiere {PDF_PATH.name} ...")
    images = analyze_pdf_images(PDF_PATH)
    print(f"  Gefunden: {len(images)} Bilder total")

    n_v4_relevant = sum(1 for img in images if img["v4_relevant"])
    print(f"  Davon V4-relevant (>={V4_MIN_PIXEL_THRESHOLD} px): {n_v4_relevant}")

    if not images:
        print("Keine Bilder im PDF gefunden. Abbruch.")
        return

    by_page = Counter(img["page"] for img in images)
    size_categories = categorize_by_size(images)

    print(f"  Speichere Stichprobe von {SAMPLE_SIZE} V4-relevanten Bildern ...")
    samples = save_sample_images(PDF_PATH, images, SAMPLE_DIR, SAMPLE_SIZE)

    report = {
        "pdf_path": str(PDF_PATH),
        "total_images": len(images),
        "v4_relevant_count": n_v4_relevant,
        "excluded_count": len(images) - n_v4_relevant,
        "v4_min_pixel_threshold": V4_MIN_PIXEL_THRESHOLD,
        "total_pages_with_images": len(by_page),
        "images_per_page": dict(by_page),
        "size_categories": size_categories,
        "samples_saved": samples,
        "raw_image_metadata": images,
    }

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    markdown = build_markdown_report(
        PDF_PATH, images, dict(by_page), size_categories, samples
    )
    MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")

    print(f"\nReport: {MARKDOWN_REPORT}")
    print(f"Samples: {SAMPLE_DIR}")
    print(f"JSON-Detail: {REPORT_PATH}")

    print("\nGrössenverteilung:")
    for cat in ["tiny", "small", "medium", "large"]:
        count = size_categories.get(cat, 0)
        pct = 100 * count / max(len(images), 1)
        relevant_mark = " (V4-relevant)" if cat in ("medium", "large") else ""
        print(f"  {cat} ({_size_desc(cat)}): {count} ({pct:.1f}%){relevant_mark}")

    print(
        f"\nKostenschätzung gpt-4o-mini:"
        f" ${n_v4_relevant * GPT_4O_MINI_COST_PER_IMAGE_MIN:.2f}"
        f" - ${n_v4_relevant * GPT_4O_MINI_COST_PER_IMAGE_MAX:.2f}"
    )
    print(
        f"Kostenschätzung gpt-4o:"
        f" ${n_v4_relevant * GPT_4O_COST_PER_IMAGE_MIN:.2f}"
        f" - ${n_v4_relevant * GPT_4O_COST_PER_IMAGE_MAX:.2f}"
    )
    print(
        f"Geschätzte Lauf-Zeit (sequenziell, 3s/Bild):"
        f" ~{n_v4_relevant * 3 // 60} Minuten"
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    main()
