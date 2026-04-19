"""Auswertung aller Handbücher in data/raw/handbuecher.

Analysiert alle PDFs und schreibt einen Report nach
data/eval/handbuecher_report.txt.

Metriken:
- Dokumentumfang:    Seitenzahl, Textabdeckung, Wörter, Zeichen/Seite
- Strukturierungsgrad: Hierarchietiefe, Wörter/Abschnitt, Überschriften/Seite
- Multimodalität:    Bild-Dichte, Tabellen-Frequenz
"""

import datetime
import logging
import re
import statistics
from pathlib import Path

from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HANDBUCH_DIR = PROJECT_ROOT / "data" / "raw" / "handbuecher"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
REPORT: Path = EVAL_DIR / "handbuecher_report.txt"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Zählt Wörter anhand von Whitespace-Trennung."""
    return len(text.split())


def _count_images_fast(page) -> int:
    """Zählt Bild-XObjects auf einer Seite ohne Dekompression.

    Liest nur die /Resources-Metadaten der Seite, ohne die Bilddaten zu
    dekomprimieren. Deutlich schneller als page.images.
    """
    try:
        resources = page.get("/Resources")
        if resources is None:
            return 0
        xobjects = resources.get("/XObject", {})
        if not xobjects:
            return 0
        return sum(
            1
            for key in xobjects
            if xobjects[key].get("/Subtype") == "/Image"
        )
    except Exception:
        return 0


def _outline_stats(nodes: list, depth: int = 0) -> tuple[int, int]:
    """Traversiert den Inhaltsverzeichnis-Baum rekursiv.

    Returns:
        (Gesamtanzahl Einträge, maximale Verschachtelungstiefe)
    """
    total = 0
    max_depth = depth
    for item in nodes:
        if isinstance(item, list):
            sub_total, sub_depth = _outline_stats(item, depth + 1)
            total += sub_total
            max_depth = max(max_depth, sub_depth)
        else:
            total += 1
            max_depth = max(max_depth, depth)
    return total, max_depth


def _depth_distribution(nodes: list, depth: int = 0) -> dict[int, int]:
    """Zählt Outline-Einträge pro Tiefenebene."""
    dist: dict[int, int] = {}
    for item in nodes:
        if isinstance(item, list):
            sub = _depth_distribution(item, depth + 1)
            for d, c in sub.items():
                dist[d] = dist.get(d, 0) + c
        else:
            dist[depth] = dist.get(depth, 0) + 1
    return dist


# ---------------------------------------------------------------------------
# Haupt-Analysefunktion
# ---------------------------------------------------------------------------


RE_TABELLE = re.compile(r"Tabelle\s+\d", re.IGNORECASE)


def analyse_pdf(pdf_path: Path) -> dict:
    """Analysiert ein einzelnes PDF und gibt alle Metriken als Dict zurück."""
    reader = PdfReader(pdf_path)
    n_pages = len(reader.pages)
    logger.info("Analysiere %s  (%d Seiten)", pdf_path.name, n_pages)

    # ── Textextraktion und Bild/Tabellen-Erkennung in einem Durchlauf ────────
    text_pages: list[str] = []
    pages_with_text = 0
    total_words = 0
    total_chars = 0
    pages_with_image = 0
    total_images = 0
    pages_with_table = 0

    for i, page in enumerate(reader.pages, start=1):
        if i % 500 == 0:
            logger.info("  … %d / %d Seiten verarbeitet", i, n_pages)

        text = page.extract_text() or ""
        text_pages.append(text)

        if text.strip():
            pages_with_text += 1
            total_words += _word_count(text)
            total_chars += len(text)

        if RE_TABELLE.search(text):
            pages_with_table += 1

        n_imgs = _count_images_fast(page)
        total_images += n_imgs
        if n_imgs > 0:
            pages_with_image += 1

    avg_words_per_page = total_words / n_pages if n_pages else 0
    avg_chars_per_page = total_chars / n_pages if n_pages else 0
    image_density = n_pages / pages_with_image if pages_with_image else float("inf")

    # ── Tabellen (Caption-basiert) ────────────────────────────────────────────
    # Heuristik: Seite enthält das Muster „Tabelle <Zahl>" → formelle Tabelle.
    # SelectLine-Handbücher verwenden selten formale Tabellen;
    # die meisten Darstellungen sind Screenshots (s. Bild-Dichte).
    table_density = (
        n_pages / pages_with_table if pages_with_table else float("inf")
    )

    # ── Outline / Strukturierungsgrad ─────────────────────────────────────────
    outline = reader.outline
    n_headings, max_depth = _outline_stats(outline)
    depth_dist = _depth_distribution(outline)

    avg_words_per_section = total_words / n_headings if n_headings else 0
    avg_headings_per_page = n_headings / n_pages if n_pages else 0

    return {
        "name": pdf_path.stem,
        "n_pages": n_pages,
        "pages_with_text": pages_with_text,
        "text_coverage_pct": pages_with_text / n_pages * 100 if n_pages else 0,
        "total_words": total_words,
        "avg_words_per_page": avg_words_per_page,
        "avg_chars_per_page": avg_chars_per_page,
        "n_headings": n_headings,
        "max_heading_depth": max_depth,
        "depth_dist": depth_dist,
        "avg_words_per_section": avg_words_per_section,
        "avg_headings_per_page": avg_headings_per_page,
        "total_images": total_images,
        "pages_with_image": pages_with_image,
        "image_density": image_density,
        "pages_with_table": pages_with_table,
        "table_density": table_density,
    }


# ---------------------------------------------------------------------------
# Report-Generierung
# ---------------------------------------------------------------------------


def _short_name(full_name: str) -> str:
    """Kürzt den Dateinamen auf einen lesbaren Handbuchnamen."""
    return (
        full_name.replace("SelectLine ", "")
        .replace(" Handbuch CH Aktuelle Version", "")
        .strip()
    )


def generate_report(pdfs: list[dict]) -> str:
    """Erstellt den Auswertungs-Report als String."""
    lines: list[str] = []

    def h1(title: str) -> None:
        lines.append("\n" + "=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def h2(title: str) -> None:
        lines.append(f"\n--- {title} ---")

    def density_str(d: float) -> str:
        if d == float("inf"):
            return "keine"
        return f"jede {d:.1f}. Seite"

    # ── Kopf ─────────────────────────────────────────────────────────────────
    lines.append("HANDBUCH-AUSWERTUNG – SelectLine Produktdokumentation")
    lines.append(f"Erstellt: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Quellordner: {HANDBUCH_DIR.name}")

    total_pages = sum(d["n_pages"] for d in pdfs)
    lines.append(f"\nAnzahl Handbücher:        {len(pdfs)}")
    lines.append(f"Gesamtseitenanzahl:       {total_pages}")

    # ── 1. Dokumentumfang ────────────────────────────────────────────────────
    h1("1. DOKUMENTUMFANG")

    col_w = 38
    lines.append(
        f"{'Handbuch':<{col_w}}  {'Seiten':>6}  {'Textseiten':>10}  "
        f"{'Text-%':>6}  {'Wörter':>8}  {'∅ Wörter/S':>10}  {'∅ Zeich/S':>9}"
    )
    lines.append("-" * 95)

    for d in pdfs:
        name = _short_name(d["name"])[:col_w]
        lines.append(
            f"{name:<{col_w}}  {d['n_pages']:>6}  {d['pages_with_text']:>10}  "
            f"{d['text_coverage_pct']:>5.1f}%  {d['total_words']:>8}  "
            f"{d['avg_words_per_page']:>10.1f}  {d['avg_chars_per_page']:>9.0f}"
        )

    # Gesamt-Zeile
    lines.append("-" * 95)
    all_tw = sum(d["total_words"] for d in pdfs)
    all_pt = sum(d["pages_with_text"] for d in pdfs)
    avg_wpp = sum(d["avg_words_per_page"] for d in pdfs) / len(pdfs)
    avg_cpp = sum(d["avg_chars_per_page"] for d in pdfs) / len(pdfs)
    lines.append(
        f"{'GESAMT':<{col_w}}  {total_pages:>6}  {all_pt:>10}  "
        f"{all_pt/total_pages*100:>5.1f}%  {all_tw:>8}  "
        f"{avg_wpp:>10.1f}  {avg_cpp:>9.0f}"
    )

    # ── 2. Strukturierungsgrad ────────────────────────────────────────────────
    h1("2. STRUKTURIERUNGSGRAD")

    lines.append(
        f"{'Handbuch':<{col_w}}  {'Überschriften':>13}  {'Max-Tiefe':>9}  "
        f"{'∅ Wörter/Abschnitt':>18}  {'∅ Überschr./Seite':>18}"
    )
    lines.append("-" * 95)

    for d in pdfs:
        name = _short_name(d["name"])[:col_w]
        lines.append(
            f"{name:<{col_w}}  {d['n_headings']:>13}  {d['max_heading_depth']:>9}  "
            f"{d['avg_words_per_section']:>18.1f}  {d['avg_headings_per_page']:>18.2f}"
        )

    h2("Hierarchie-Tiefenverteilung (Anzahl Einträge je Outline-Ebene)")
    max_depth_global = max(d["max_heading_depth"] for d in pdfs)
    depth_labels = [f"Tiefe {i}" for i in range(max_depth_global + 1)]
    lines.append(
        f"{'Handbuch':<{col_w}}  " + "  ".join(f"{lbl:>9}" for lbl in depth_labels)
    )
    lines.append("-" * (col_w + 2 + 11 * (max_depth_global + 1)))
    for d in pdfs:
        name = _short_name(d["name"])[:col_w]
        dist = d["depth_dist"]
        counts = [dist.get(i, 0) for i in range(max_depth_global + 1)]
        lines.append(
            f"{name:<{col_w}}  " + "  ".join(f"{c:>9}" for c in counts)
        )

    # ── 3. Multimodalität ────────────────────────────────────────────────────
    h1("3. MULTIMODALITÄT")

    lines.append(
        "Bild-Dichte:      Seiten mit mindestens einem eingebetteten Bild-XObject"
    )
    lines.append(
        "Tabellen-Frequenz: Seiten mit Beschriftung 'Tabelle <Nr.>' (formelle Tabellen)"
    )
    lines.append("")
    lines.append(
        f"{'Handbuch':<{col_w}}  {'Bildseiten':>10}  {'Bilder insg.':>12}  "
        f"{'Bild-Dichte':>18}  {'Tabellenseiten':>14}  {'Tabellen-Freq.':>15}"
    )
    lines.append("-" * 97)

    for d in pdfs:
        name = _short_name(d["name"])[:col_w]
        img_dens = density_str(d["image_density"])
        tab_dens = density_str(d["table_density"])
        lines.append(
            f"{name:<{col_w}}  {d['pages_with_image']:>10}  {d['total_images']:>12}  "
            f"{img_dens:>18}  {d['pages_with_table']:>14}  {tab_dens:>15}"
        )

    # Gesamtstatistik Bilder
    h2("Gesamtstatistik Bilder")
    all_img_pages = sum(d["pages_with_image"] for d in pdfs)
    all_imgs = sum(d["total_images"] for d in pdfs)
    lines.append(f"Seiten mit Bild insgesamt:    {all_img_pages}")
    lines.append(f"Bilder insgesamt:             {all_imgs}")
    lines.append(
        f"Gesamt-Bild-Dichte:           jede "
        f"{total_pages / all_img_pages:.1f}. Seite"
        if all_img_pages else "Gesamt-Bild-Dichte:           keine Bilder"
    )

    h2("Gesamtstatistik Tabellen")
    all_tab_pages = sum(d["pages_with_table"] for d in pdfs)
    lines.append(f"Seiten mit formeller Tabelle: {all_tab_pages}")
    if all_tab_pages:
        lines.append(
            f"Gesamt-Tabellen-Dichte:       jede "
            f"{total_pages / all_tab_pages:.1f}. Seite"
        )
    else:
        lines.append(
            "Gesamt-Tabellen-Dichte:       keine formellen Tabellen gefunden"
        )
    lines.append(
        "\nHinweis: SelectLine-Handbücher nutzen vorwiegend Screenshots statt"
    )
    lines.append(
        "         formeller Tabellen. Die Bild-Dichte erfasst diesen Anteil."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
    """Hauptfunktion: analysiert alle PDFs, erstellt Report, schreibt Datei."""
    pdf_files = sorted(HANDBUCH_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error("Keine PDFs in %s gefunden.", HANDBUCH_DIR)
        return

    logger.info("Gefunden: %d PDFs in %s", len(pdf_files), HANDBUCH_DIR)
    results = [analyse_pdf(p) for p in pdf_files]

    report = generate_report(results)
    print(report)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    logger.info("Report gespeichert: %s", REPORT)


if __name__ == "__main__":
    main()
