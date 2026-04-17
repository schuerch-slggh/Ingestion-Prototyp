"""Auswertung der SelectLine Helpdesk Vorgänge (vorgaenge.csv).

Analysiert die Ticket-Tabelle und schreibt einen Report nach
data/eval/ticket_report.txt.
"""

import csv
import datetime
import logging
import statistics
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCE: Path = INTERIM_DIR / "vorgaenge.csv"
REPORT: Path = EVAL_DIR / "ticket_report.txt"

csv.field_size_limit(10_000_000)

RAG_FIELDS: list[str] = [
    "ID", "KATEGORIE", "VERSION", "VERSIONERL",
    "BESCHREIBU", "PRODUKTID", "FEHLER", "LOESUNG",
    "STATUSID", "BEARBEITET",
]
STRUCTURED_FIELDS: list[str] = [
    "BEARBEITET", "ID", "PRODUKTID", "STATUSID", "VERSION", "VERSIONERL",
]
UNSTRUCTURED_FIELDS: list[str] = [
    "BESCHREIBU", "FEHLER", "KATEGORIE", "LOESUNG",
]

PRODUKT_NAMES: dict[str, str] = {
    "1": "Auftrag",
    "2": "Rechnungswesen",
    "3": "Lohn",
    "4": "Kassabuch",
    "5": "Leistung",
    "6": "PC Kasse",
    "7": "Vertriebsmodul",
    "8": "Datenorm/Artikelmanager",
    "9": "WAG Auftrag",
    "10": "WAG Fibu",
    "11": "WAG Lohn",
    "12": "Toolbox",
    "13": "Systemübergreifend",
    "14": "Anlagebuchhaltung",
    "15": "OP-Verwaltung",
    "16": "Helpdesk",
    "17": "Internetauftritt",
    "18": "Verkauf",
    "19": "Mapkit",
    "20": "CRM",
    "21": "SL.mobile",
    "22": "Plantafel",
    "23": "/",
    "24": "Makro SQL",
    "25": "Power BI",
    "26": "SL.MDE",
    "27": "SL.Archiv",
    "28": "SelectLine Server",
    "0": "ID 0",
    "": "ID",
}

STATUS_NAMES: dict[str, str] = {
    "1000": "Erledigt",
    "12": "SLDE",
    "7": "Zu Bearbeiten",
    "21": "Wiedereröffnet",
    "13": "Zu Besprechen",
    "1": "Aufgenommen",
    "17": "Abgebrochen",
    "8": "Zu Testen",
}


def load_tickets(source: Path) -> list[dict[str, str]]:
    """Lädt das CSV und gibt alle Datensätze als Liste von Dicts zurück."""
    with open(source, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _word_count(text: str) -> int:
    """Zählt Wörter anhand von Whitespace-Trennung."""
    return len(text.split())


def _first_n_words(text: str, n: int = 12) -> str:
    """Gibt die ersten n Wörter eines Textes zurück."""
    return " ".join(text.split()[:n])


def _count_duplicates(values: list[str]) -> tuple[int, int]:
    """Zählt Einträge, die mindestens zweimal vorkommen.

    Returns:
        (Anzahl doppelter Einträge, Anzahl distincter Werte mehrfach)
    """
    counter = Counter(values)
    dup_vals = [(v, c) for v, c in counter.items() if c >= 2]
    return sum(c for _, c in dup_vals), len(dup_vals)


def _count_similar(values: list[str], n: int = 12) -> tuple[int, int]:
    """Zählt Einträge in Gruppen, wo erste n Wörter übereinstimmen,
    aber die Texte innerhalb der Gruppe nicht alle identisch sind.

    Returns:
        (Anzahl ähnlicher Einträge, Anzahl solcher Gruppen)
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for v in values:
        groups[_first_n_words(v, n)].append(v)

    count = 0
    num_groups = 0
    for group in groups.values():
        if len(group) >= 2 and len(set(group)) >= 2:
            count += len(group)
            num_groups += 1
    return count, num_groups


def generate_report(rows: list[dict[str, str]]) -> str:
    """Erstellt den Auswertungs-Report als String."""
    lines: list[str] = []
    n = len(rows)

    def h1(title: str) -> None:
        lines.append("\n" + "=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def h2(title: str) -> None:
        lines.append(f"\n--- {title} ---")

    def pct(count: int, total: int = n) -> str:
        return f"{count / total * 100:.1f} %"

    # ── Kopf ────────────────────────────────────────────────────────────────
    lines.append("TICKET-AUSWERTUNG – SelectLine Helpdesk Vorgänge")
    lines.append(f"Erstellt: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Quelldatei: {SOURCE.name}")

    # ── 1. Umfang und Struktur ───────────────────────────────────────────────
    h1("1. UMFANG UND STRUKTUR")

    n_rag = len(RAG_FIELDS)
    n_struct = len(STRUCTURED_FIELDS)
    n_unstruct = len(UNSTRUCTURED_FIELDS)
    rag_field_str = ", ".join(RAG_FIELDS)
    struct_str = ", ".join(STRUCTURED_FIELDS)
    unstruct_str = ", ".join(UNSTRUCTURED_FIELDS)

    lines.append(f"Anzahl Tickets insgesamt:             {n}")
    lines.append(
        f"RAG-relevante Felder ({n_rag}):         {rag_field_str}"
    )
    lines.append(f"  davon strukturiert ({n_struct}):          {struct_str}")
    lines.append(
        f"  davon semi-/unstrukturiert ({n_unstruct}): {unstruct_str}"
    )
    lines.append("")
    lines.append(
        f"  Anteil strukturiert:             "
        f"{n_struct / n_rag * 100:.0f} %  ({n_struct} / {n_rag} RAG-Felder)"
    )
    lines.append(
        f"  Anteil semi-/unstrukturiert:     "
        f"{n_unstruct / n_rag * 100:.0f} %  ({n_unstruct} / {n_rag} RAG-Felder)"
    )

    prod_vals = [r["PRODUKTID"] for r in rows]
    kat_vals = [r["KATEGORIE"] for r in rows]
    n_produkte = len(set(prod_vals))
    n_kategorien = len({k for k in kat_vals if k and k != "0"})

    lines.append("")
    lines.append(
        f"Unterschiedliche Modulbereiche (PRODUKTID):     {n_produkte}"
    )
    lines.append(
        f"Unterschiedliche Kategorien (KATEGORIE):        {n_kategorien}"
    )

    h2("Verteilung nach Produkt (PRODUKTID)")
    lines.append(f"{'Produkt':<33}  {'Anzahl':>6}  {'Anteil':>6}")
    lines.append("-" * 50)
    for pid, cnt in Counter(prod_vals).most_common():
        name = PRODUKT_NAMES.get(pid, f"ID {pid}")
        lines.append(f"{name:<33}  {cnt:>6}  {pct(cnt):>6}")

    # ── 2. Vollständigkeit ───────────────────────────────────────────────────
    h1("2. VOLLSTÄNDIGKEIT")

    beschr_short = sum(1 for r in rows if _word_count(r["BESCHREIBU"]) < 4)
    mit_fehler = sum(1 for r in rows if r["FEHLER"].strip())
    mit_loesung = sum(1 for r in rows if r["LOESUNG"].strip())
    mit_beiden = sum(
        1 for r in rows if r["FEHLER"].strip() and r["LOESUNG"].strip()
    )
    fehler_near_empty = sum(
        1 for r in rows if r["FEHLER"].strip() and _word_count(r["FEHLER"]) < 4
    )
    loesung_near_empty = sum(
        1 for r in rows
        if r["LOESUNG"].strip() and _word_count(r["LOESUNG"]) < 4
    )
    ohne_version = sum(1 for r in rows if not r["VERSION"].strip())
    ohne_kategorie = sum(
        1 for r in rows
        if not r["KATEGORIE"].strip() or r["KATEGORIE"].strip() == "0"
    )

    lines.append(
        f"Beschreibung < 4 Wörter:              "
        f"{beschr_short:>4}  ({pct(beschr_short)})"
    )
    lines.append(
        f"Mit Fehlertext (FEHLER nicht leer):  "
        f"{mit_fehler:>5}  ({pct(mit_fehler)})"
    )
    lines.append(
        f"Mit Lösungstext (LOESUNG nicht leer):  "
        f"{mit_loesung:>4}  ({pct(mit_loesung)})"
    )
    lines.append(
        f"Mit Fehler UND Lösung:                "
        f"{mit_beiden:>4}  ({pct(mit_beiden)})"
    )
    lines.append("")
    lines.append(
        f"Nahezu leere FEHLER-Einträge (< 4 Wörter, aber nicht leer):     "
        f"{fehler_near_empty:>3}  ({pct(fehler_near_empty)})"
    )
    lines.append(
        f"Nahezu leere LOESUNG-Einträge (< 4 Wörter, aber nicht leer):    "
        f"{loesung_near_empty:>3}  ({pct(loesung_near_empty)})"
    )
    lines.append("")
    lines.append(
        f"Ohne Version (VERSION leer):          "
        f"{ohne_version:>4}  ({pct(ohne_version)})"
    )
    lines.append(
        f"Ohne Modul/Kategorie (KATEGORIE leer oder 0):  "
        f"{ohne_kategorie:>4}  ({pct(ohne_kategorie)})"
    )

    # ── 3. Textqualität und Informationsdichte ──────────────────────────────
    h1("3. TEXTQUALITÄT UND INFORMATIONSDICHTE")

    for field, label in [
        ("BESCHREIBU", "Beschreibung (BESCHREIBU)"),
        ("FEHLER", "Fehler (FEHLER)"),
        ("LOESUNG", "Lösung (LOESUNG)"),
    ]:
        non_empty_wc = sorted(
            _word_count(r[field]) for r in rows if r[field].strip()
        )
        ne = len(non_empty_wc)
        avg = sum(non_empty_wc) / ne
        med = statistics.median(non_empty_wc)
        under_30 = sum(1 for wc in non_empty_wc if wc < 30)
        between_30_100 = sum(1 for wc in non_empty_wc if 30 <= wc <= 100)
        over_100 = sum(1 for wc in non_empty_wc if wc > 100)

        h2(f"Textlänge (Wörter) – {label}")
        lines.append(f"  Einträge (nicht leer):     {ne:>5}")
        lines.append(f"  Durchschnitt:              {avg:>10.1f}")
        lines.append(f"  Median:                    {med:>10.1f}")
        lines.append(f"  Minimum:                   {non_empty_wc[0]:>11}")
        lines.append(f"  Maximum:                   {non_empty_wc[-1]:>11}")
        lines.append("")
        lines.append(
            f"  Verteilung der Textlängen (von {ne} nicht-leeren Einträgen):"
        )
        lines.append(
            f"    < 30 Wörter:    {under_30:>5}  ({pct(under_30, ne)})"
        )
        lines.append(
            f"    30–100 Wörter:  {between_30_100:>5}  ({pct(between_30_100, ne)})"
        )
        lines.append(
            f"    > 100 Wörter:   {over_100:>5}  ({pct(over_100, ne)})"
        )

    loesung_short = sum(
        1 for r in rows
        if r["LOESUNG"].strip() and _word_count(r["LOESUNG"]) < 10
    )
    h2("Sehr kurze Lösungstexte (< 10 Wörter, unter allen Tickets)")
    lines.append(f"    {loesung_short}  ({pct(loesung_short)} aller Tickets)")

    # ── 4. Konsistenz und Dubletten ─────────────────────────────────────────
    h1("4. KONSISTENZ UND DUBLETTEN")

    beschr_vals = [r["BESCHREIBU"] for r in rows]
    fehler_vals = [r["FEHLER"] for r in rows]
    loesung_vals = [r["LOESUNG"] for r in rows]

    beschr_dup, beschr_dup_d = _count_duplicates(beschr_vals)
    fehler_dup, fehler_dup_d = _count_duplicates(fehler_vals)
    loesung_dup, loesung_dup_d = _count_duplicates(loesung_vals)

    lines.append(
        f"Identische Beschreibungen:           "
        f"{beschr_dup:>4}  ({pct(beschr_dup)})  "
        f"[{beschr_dup_d} distinct Werte mehrfach]"
    )
    lines.append(
        f"Identische Fehlertexte:             "
        f"{fehler_dup:>5}  ({pct(fehler_dup)})  "
        f"[{fehler_dup_d} distinct Werte mehrfach]"
    )
    lines.append(
        f"Identische Lösungstexte:             "
        f"{loesung_dup:>4}  ({pct(loesung_dup)})  "
        f"[{loesung_dup_d} distinct Werte mehrfach]"
    )

    beschr_sim, beschr_sim_g = _count_similar(beschr_vals)
    fehler_sim, fehler_sim_g = _count_similar(fehler_vals)

    h2("Sehr ähnliche Beschreibungen (gleiche ersten 12 Wörter)")
    lines.append(
        f"     {beschr_sim}  ({pct(beschr_sim)})  "
        f"[{beschr_sim_g} Gruppen ähnlicher Betreffe]"
    )

    h2("Sehr ähnliche Fehlertexte (gleiche ersten 12 Wörter)")
    lines.append(
        f"    {fehler_sim}  ({pct(fehler_sim)})  "
        f"[{fehler_sim_g} Gruppen ähnlicher Fehlertexte]"
    )

    # ── 5. Zeitliche Einordnung ─────────────────────────────────────────────
    h1("5. ZEITLICHE EINORDNUNG")

    h2("Verteilung nach Modulbereich / Produkt (PRODUKTID)")
    lines.append(f"{'Produkt / Modul':<35}  {'Anzahl':>6}  {'Anteil':>6}")
    lines.append("-" * 52)
    for pid, cnt in Counter(prod_vals).most_common():
        name = PRODUKT_NAMES.get(pid, f"ID {pid}")
        lines.append(f"{name:<35}  {cnt:>6}  {pct(cnt):>6}")

    h2("Verteilung nach Version (Top 25, ohne leere)")
    version_vals = [r["VERSION"].strip() for r in rows if r["VERSION"].strip()]
    version_counter = Counter(version_vals)
    lines.append(f"{'Version':<22}  {'Anzahl':>6}  {'Anteil':>6}")
    lines.append("-" * 40)
    for ver, cnt in version_counter.most_common(25):
        lines.append(f"{ver:<22}  {cnt:>6}  {pct(cnt):>6}")

    h2("Verteilung nach Ticketstatus (STATUSID)")
    status_counter = Counter(r["STATUSID"] for r in rows)
    lines.append(f"{'Status':<40}  {'Anzahl':>6}  {'Anteil':>6}")
    lines.append("-" * 58)
    for sid, cnt in status_counter.most_common():
        name = STATUS_NAMES.get(sid)
        if name:
            lines.append(f"{name:<40}  {cnt:>6}  {pct(cnt):>6}")

    return "\n".join(lines)


def main() -> None:
    """Hauptfunktion: lädt Daten, erstellt Report, speichert Ergebnis."""
    logger.info("Lade %s", SOURCE)
    rows = load_tickets(SOURCE)
    logger.info("Tickets geladen: %d", len(rows))

    report = generate_report(rows)
    print(report)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    logger.info("Report gespeichert: %s", REPORT)


if __name__ == "__main__":
    main()
