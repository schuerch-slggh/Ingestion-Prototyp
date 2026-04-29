"""Auswertung aller Schulungsunterlagen in data/raw/schulungsunterlagen.

Analysiert alle PDFs im Verzeichnis und schreibt einen Report nach
data/eval/schulungsunterlagen_report.txt.

Metriken:
- Dokumentumfang:      Seitenzahl, Textabdeckung, Wörter, Zeichen/Seite
- Strukturierungsgrad: Hierarchietiefe, Wörter/Abschnitt, Überschriften/Seite
- Multimodalität:      Bild-Dichte, Text-zu-Bild-Verhältnis, Tabellen-Frequenz
"""

import datetime
import logging
import re
from pathlib import Path

from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "schulungsunterlagen"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
REPORT: Path = EVAL_DIR / "schulungsunterlagen_report.txt"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RE_TABELLE = re.compile(r"Tabelle\s+\d", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Zählt Wörter anhand von Whitespace-Trennung."""
    return len(text.split())


def _count_images_fast(page) -> int:
    """Zählt Bild-XObjects auf einer Seite ohne Dekompression."""
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
    """Traversiert den Outline-Baum rekursiv.

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


def _short_name(stem: str) -> str:
    """Kürzt den Dateinamen für die Anzeige (entfernt 'Schulungsunterlagen ')."""
    for prefix in ("Schulungsunterlagen ", "Schulungsunterrlagen "):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


# ---------------------------------------------------------------------------
# PDF-Analyse
# ---------------------------------------------------------------------------


def analyse_pdf(pdf_path: Path) -> dict:
    """Analysiert ein einzelnes PDF und gibt alle Metriken als Dict zurück."""
    reader = PdfReader(pdf_path)
    n_pages = len(reader.pages)
    logger.info("  %s  (%d S.)", pdf_path.name[:70], n_pages)

    pages_with_text = 0
    total_words = 0
    total_chars = 0
    pages_with_image = 0
    total_images = 0
    pages_with_table = 0

    for page in reader.pages:
        text = page.extract_text() or ""

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
    table_density = n_pages / pages_with_table if pages_with_table else float("inf")
    chars_per_image = total_chars / total_images if total_images else float("inf")

    outline = reader.outline
    n_headings, max_depth = _outline_stats(outline)
    depth_dist = _depth_distribution(outline)
    avg_words_per_section = total_words / n_headings if n_headings else 0
    avg_headings_per_page = n_headings / n_pages if n_pages else 0

    return {
        "name": _short_name(pdf_path.stem),
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
        "chars_per_image": chars_per_image,
        "pages_with_table": pages_with_table,
        "table_density": table_density,
    }


# ---------------------------------------------------------------------------
# Report-Generierung
# ---------------------------------------------------------------------------


def _density_str(d: float) -> str:
    """Formatiert eine Seitendichte als lesbare Zeichenkette."""
    if d == float("inf"):
        return "keine"
    return f"jede {d:.1f}. S."


def _chars_per_img_str(v: float) -> str:
    """Formatiert das Text-zu-Bild-Verhältnis."""
    if v == float("inf"):
        return "kein Bild"
    return f"{v:.0f} Z./Bild"


def _aggregate(pdfs: list[dict]) -> dict:
    """Berechnet aggregierte Werte über alle PDFs."""
    n_docs = len(pdfs)
    n_pages = sum(d["n_pages"] for d in pdfs)
    pages_with_text = sum(d["pages_with_text"] for d in pdfs)
    total_words = sum(d["total_words"] for d in pdfs)
    total_chars = sum(d["avg_chars_per_page"] * d["n_pages"] for d in pdfs)
    total_images = sum(d["total_images"] for d in pdfs)
    pages_with_image = sum(d["pages_with_image"] for d in pdfs)
    pages_with_table = sum(d["pages_with_table"] for d in pdfs)
    n_headings = sum(d["n_headings"] for d in pdfs)
    max_depth = max((d["max_heading_depth"] for d in pdfs), default=0)

    avg_wpp = total_words / n_pages if n_pages else 0
    avg_cpp = total_chars / n_pages if n_pages else 0
    img_density = n_pages / pages_with_image if pages_with_image else float("inf")
    tab_density = n_pages / pages_with_table if pages_with_table else float("inf")
    chars_per_img = total_chars / total_images if total_images else float("inf")
    avg_wps = total_words / n_headings if n_headings else 0
    avg_hpp = n_headings / n_pages if n_pages else 0

    return {
        "n_docs": n_docs,
        "n_pages": n_pages,
        "pages_with_text": pages_with_text,
        "text_coverage_pct": pages_with_text / n_pages * 100 if n_pages else 0,
        "total_words": total_words,
        "avg_words_per_page": avg_wpp,
        "avg_chars_per_page": avg_cpp,
        "n_headings": n_headings,
        "max_heading_depth": max_depth,
        "avg_words_per_section": avg_wps,
        "avg_headings_per_page": avg_hpp,
        "total_images": total_images,
        "pages_with_image": pages_with_image,
        "image_density": img_density,
        "chars_per_image": chars_per_img,
        "pages_with_table": pages_with_table,
        "table_density": tab_density,
    }


def generate_report(all_pdfs: list[dict]) -> str:
    """Erstellt den vollständigen Auswertungs-Report als String."""
    lines: list[str] = []

    def h1(title: str) -> None:
        lines.append("\n" + "=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def h2(title: str) -> None:
        lines.append(f"\n--- {title} ---")

    agg = _aggregate(all_pdfs)
    CW = 38  # column width for document names

    # ── Kopf ─────────────────────────────────────────────────────────────────
    lines.append("SCHULUNGSUNTERLAGEN-AUSWERTUNG – SelectLine")
    lines.append(f"Erstellt: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Quellordner: {SOURCE_DIR.name}")
    lines.append(f"\nAnzahl Dokumente:         {agg['n_docs']}")
    lines.append(f"Gesamtseitenanzahl:       {agg['n_pages']}")
    lines.append(f"Gesamtwörter:             {agg['total_words']}")

    # ── 1. Dokumentumfang ────────────────────────────────────────────────────
    h1("1. DOKUMENTUMFANG")
    hdr = (
        f"{'Schulungsunterlage':<{CW}}  {'Seiten':>6}  {'Text-%':>6}  "
        f"{'Wörter':>7}  {'∅W/S':>6}  {'∅Z/S':>6}"
    )
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for d in all_pdfs:
        name = d["name"][:CW]
        lines.append(
            f"{name:<{CW}}  {d['n_pages']:>6}  "
            f"{d['text_coverage_pct']:>5.1f}%  "
            f"{d['total_words']:>7}  {d['avg_words_per_page']:>6.1f}  "
            f"{d['avg_chars_per_page']:>6.0f}"
        )

    lines.append("-" * len(hdr))
    lines.append(
        f"{'GESAMT':<{CW}}  {agg['n_pages']:>6}  "
        f"{agg['text_coverage_pct']:>5.1f}%  "
        f"{agg['total_words']:>7}  {agg['avg_words_per_page']:>6.1f}  "
        f"{agg['avg_chars_per_page']:>6.0f}"
    )

    # ── 2. Strukturierungsgrad ────────────────────────────────────────────────
    h1("2. STRUKTURIERUNGSGRAD")
    lines.append(
        "Hierarchietiefe basiert auf der PDF-Outline (Lesezeichen)."
    )
    lines.append(
        "Dokumente ohne Outline-Einträge haben 0 Überschriften."
    )

    hdr2 = (
        f"{'Schulungsunterlage':<{CW}}  {'Überschr.':>9}  {'MaxTiefe':>8}  "
        f"{'∅W/Abschn.':>10}  {'∅Überschr/S':>11}"
    )
    lines.append(hdr2)
    lines.append("-" * len(hdr2))

    for d in all_pdfs:
        name = d["name"][:CW]
        lines.append(
            f"{name:<{CW}}  {d['n_headings']:>9}  "
            f"{d['max_heading_depth']:>8}  "
            f"{d['avg_words_per_section']:>10.1f}  "
            f"{d['avg_headings_per_page']:>11.2f}"
        )

    lines.append("-" * len(hdr2))
    lines.append(
        f"{'GESAMT':<{CW}}  {agg['n_headings']:>9}  "
        f"{agg['max_heading_depth']:>8}  "
        f"{agg['avg_words_per_section']:>10.1f}  "
        f"{agg['avg_headings_per_page']:>11.2f}"
    )

    # Tiefenverteilung für Dokumente mit Outline
    pdfs_with_outline = [d for d in all_pdfs if d["n_headings"] > 0]
    if pdfs_with_outline:
        h2("Tiefenverteilung (nur Dokumente mit PDF-Outline)")
        max_d_global = max(d["max_heading_depth"] for d in pdfs_with_outline)
        depth_labels = [f"T{i}" for i in range(max_d_global + 1)]
        hdr3 = (
            f"{'Schulungsunterlage':<{CW}}  {'Gesamt':>6}  {'MaxT':>4}  "
            + "  ".join(f"{lbl:>5}" for lbl in depth_labels)
        )
        lines.append(hdr3)
        lines.append("-" * len(hdr3))
        for d in pdfs_with_outline:
            name = d["name"][:CW]
            dist = d["depth_dist"]
            counts = "  ".join(
                f"{dist.get(i, 0):>5}" for i in range(max_d_global + 1)
            )
            lines.append(
                f"{name:<{CW}}  {d['n_headings']:>6}  "
                f"{d['max_heading_depth']:>4}  {counts}"
            )

    # ── 3. Multimodalität ────────────────────────────────────────────────────
    h1("3. MULTIMODALITÄT")
    lines.append(
        "Bild-Dichte:             Seiten mit mind. einem eingebetteten Bild-XObject"
    )
    lines.append(
        "Text-zu-Bild-Verhältnis: Durchschnittliche Zeichen pro eingebettetem Bild"
    )
    lines.append(
        "                         Hoch = textlastig  |  Niedrig = bildlastig"
    )
    lines.append(
        "Tabellen-Frequenz:       Seiten mit Beschriftung 'Tabelle <Nr.>'"
    )

    hdr4 = (
        f"{'Schulungsunterlage':<{CW}}  {'BiS':>4}  {'Bilder':>6}  "
        f"{'Bild-Dichte':>11}  {'Z./Bild':>10}  {'TabS':>4}  {'Tab-Freq.':>9}"
    )
    lines.append(hdr4)
    lines.append("-" * len(hdr4))

    for d in all_pdfs:
        name = d["name"][:CW]
        lines.append(
            f"{name:<{CW}}  {d['pages_with_image']:>4}  "
            f"{d['total_images']:>6}  "
            f"{_density_str(d['image_density']):>11}  "
            f"{_chars_per_img_str(d['chars_per_image']):>10}  "
            f"{d['pages_with_table']:>4}  "
            f"{_density_str(d['table_density']):>9}"
        )

    lines.append("-" * len(hdr4))
    lines.append(
        f"{'GESAMT':<{CW}}  {agg['pages_with_image']:>4}  "
        f"{agg['total_images']:>6}  "
        f"{_density_str(agg['image_density']):>11}  "
        f"{_chars_per_img_str(agg['chars_per_image']):>10}  "
        f"{agg['pages_with_table']:>4}  "
        f"{_density_str(agg['table_density']):>9}"
    )

    # ── Gesamtstatistiken ─────────────────────────────────────────────────────
    h1("GESAMTSTATISTIKEN")
    lines.append(f"Dokumente analysiert:               {agg['n_docs']:>6}")
    lines.append(f"Seiten insgesamt:                   {agg['n_pages']:>6}")
    lines.append(f"Seiten mit extrahierbarem Text:     {agg['pages_with_text']:>6}"
                 f"  ({agg['text_coverage_pct']:.1f}%)")
    lines.append(f"Wörter insgesamt:                   {agg['total_words']:>6}")
    lines.append(f"∅ Wörter/Seite:                     {agg['avg_words_per_page']:>6.1f}")
    lines.append(f"∅ Zeichen/Seite:                    {agg['avg_chars_per_page']:>6.0f}")
    lines.append(f"Überschriften (Outline):            {agg['n_headings']:>6}")
    lines.append(f"Max. Hierarchietiefe:               {agg['max_heading_depth']:>6}")
    lines.append(f"∅ Wörter je Abschnitt:              {agg['avg_words_per_section']:>6.1f}")
    lines.append(f"∅ Überschriften/Seite:              {agg['avg_headings_per_page']:>6.2f}")
    lines.append(f"Seiten mit eingebetteten Bildern:   {agg['pages_with_image']:>6}")
    lines.append(f"Bilder insgesamt:                   {agg['total_images']:>6}")
    lines.append(
        f"Gesamt-Bild-Dichte:                 "
        + _density_str(agg["image_density"])
    )
    lines.append(
        f"Gesamt Text-zu-Bild-Verhältnis:     "
        + _chars_per_img_str(agg["chars_per_image"])
    )
    lines.append(f"Seiten mit formeller Tabelle:       {agg['pages_with_table']:>6}")
    lines.append(
        f"Gesamt-Tabellen-Dichte:             "
        + _density_str(agg["table_density"])
    )
    lines.append(
        f"Dokumente mit PDF-Outline:          "
        f"{len(pdfs_with_outline):>6} / {agg['n_docs']}"
    )

    lines.append(
        "\nHinweis: Schulungsunterlagen nutzen überwiegend Screenshots."
    )
    lines.append(
        "         'Tabelle <Nr.>' wird nur bei explizit beschrifteten Tabellen gezählt."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
    """Hauptfunktion: analysiert alle PDFs, erstellt Report, schreibt Datei."""
    pdf_files = sorted(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error("Keine PDFs in %s gefunden.", SOURCE_DIR)
        return

    logger.info("Gefunden: %d PDFs in %s", len(pdf_files), SOURCE_DIR.name)
    all_pdfs = [analyse_pdf(p) for p in pdf_files]

    logger.info("Analyse abgeschlossen: %d PDFs.", len(all_pdfs))

    report = generate_report(all_pdfs)
    print(report)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    logger.info("Report gespeichert: %s", REPORT)


if __name__ == "__main__":
    main()
