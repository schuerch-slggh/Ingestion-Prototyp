"""Auswertung des SelectLine-Forum-Exports (Forum_Export_fixed.csv).

Analysiert die phpBB-Post-Tabelle und schreibt einen Report nach
data/eval/forum_report.txt.
"""

import csv
import datetime
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag.config import EVAL_DIR, INTERIM_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCE: Path = INTERIM_DIR / "Forum_Export_fixed.csv"
REPORT: Path = EVAL_DIR / "forum_report.txt"

# ---------------------------------------------------------------------------
# phpBB-Spaltenindex (Tabelle: phpbb_posts)
# ---------------------------------------------------------------------------
# 0  post_id          – Eindeutige Post-ID
# 1  topic_id         – Zugehöriger Thread
# 2  forum_id         – Forum-/Kategorie-ID (Produkt-Modul)
# 3  poster_id        – Benutzer-ID des Autors
# 4  icon_id          – Icon (immer 0)
# 5  poster_ip        – IP-Adresse des Posters
# 6  post_time        – Unix-Timestamp der Veröffentlichung
# 7  post_approved    – Freigegeben (immer 1)
# 8  post_reported    – Als Spam gemeldet (immer 0)
# 9  enable_bbcode    – BBCode aktiv (immer 1)
# 10 enable_smilies   – Smileys aktiv (meist 1)
# 11 enable_magic_url – Magic-URLs aktiv (meist 1)
# 12 enable_sig       – Signatur aktiv (meist 1)
# 13 post_username    – Anzeigename (nur bei Gast-Posts gesetzt)
# 14 post_subject     – Betreff / Titel
# 15 post_text        – Nachrichtentext (BBCode/HTML)
# 16 post_checksum    – MD5-Prüfsumme des Textes
# 17 post_attachment  – Hat Anhang (0/1)
# 18 bbcode_bitfield  – BBCode-Bitfeld (Base64)
# 19 bbcode_uid       – BBCode-UID des Posts
# 20 post_postcount   – Zählt zum Postcount (meist 1)
# 21 post_edit_time   – Unix-TS der letzten Bearbeitung (0 = nie)
# 22 post_edit_reason – Bearbeitungsgrund (immer leer)
# 23 post_edit_user   – Benutzer-ID des Bearbeiters
# 24 post_edit_count  – Anzahl Bearbeitungen
# 25 post_edit_locked – Bearbeitung gesperrt (meist 0)

COL = {
    "post_id": 0,
    "topic_id": 1,
    "forum_id": 2,
    "poster_id": 3,
    "icon_id": 4,
    "poster_ip": 5,
    "post_time": 6,
    "post_approved": 7,
    "post_reported": 8,
    "enable_bbcode": 9,
    "enable_smilies": 10,
    "enable_magic_url": 11,
    "enable_sig": 12,
    "post_username": 13,
    "post_subject": 14,
    "post_text": 15,
    "post_checksum": 16,
    "post_attachment": 17,
    "bbcode_bitfield": 18,
    "bbcode_uid": 19,
    "post_postcount": 20,
    "post_edit_time": 21,
    "post_edit_reason": 22,
    "post_edit_user": 23,
    "post_edit_count": 24,
    "post_edit_locked": 25,
}


def load_posts(source: Path) -> tuple[list[list[str]], int]:
    """Lädt das CSV und gibt nur Datensätze mit numerischer post_id zurück.

    Datensätze ohne numerische post_id sind Artefakte unquotierter
    mehrzeiliger Textfelder im phpBB-Export und werden übersprungen.

    Returns:
        Tupel (proper_rows, total_raw_rows).
    """
    with open(source, encoding="utf-8", newline="") as f:
        all_rows = list(csv.reader(f, delimiter=";"))
    proper = [r for r in all_rows if r[0].isdigit()]
    return proper, len(all_rows)


def col(rows: list[list[str]], index: int) -> list[str]:
    """Gibt alle Werte einer Spalte zurück."""
    return [r[index] for r in rows]


def generate_report(posts: list[list[str]], total_raw: int) -> str:
    """Erstellt den Auswertungs-Report als String."""
    lines: list[str] = []

    def h1(title: str) -> None:
        lines.append("\n" + "=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def h2(title: str) -> None:
        lines.append(f"\n--- {title} ---")

    n = len(posts)
    broken = total_raw - n

    # ── Kopf ────────────────────────────────────────────────────────────────
    lines.append("FORUM-EXPORT AUSWERTUNG – SelectLine Community Forum")
    lines.append(f"Erstellt: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Quelldatei: {SOURCE.name}")

    # ── 1. Datei-Übersicht ──────────────────────────────────────────────────
    h1("1. DATEI-ÜBERSICHT")
    lines.append(f"Rohdatensätze (CSV-Zeilen total):   {total_raw:>7}")
    lines.append(f"Gültige Posts (numerische post_id): {n:>7}")
    lines.append(
        f"Artefakt-Zeilen (unquotierte \\n):   {broken:>7}  "
        f"({broken / total_raw * 100:.1f} %)"
    )
    lines.append(f"Spalten pro Datensatz:              {len(posts[0]):>7}")
    lines.append(
        "\nHinweis: Der phpBB-Export quotiert mehrzeilige post_text-Felder\n"
        "nicht immer korrekt. Zeilen ohne numerische post_id (Artefakte)\n"
        "sind Fortsetzungen solcher Felder und wurden herausgefiltert.\n"
        "Die zugehörigen post_text-Inhalte sind in diesen Fällen gekürzt."
    )

    # ── 2. Spalten-Beschreibung ─────────────────────────────────────────────
    h1("2. SPALTEN-BESCHREIBUNG (phpBB-Schema)")
    col_desc = [
        ("0",  "post_id",        "Eindeutige Post-ID (PK)"),
        ("1",  "topic_id",       "Thread-ID; mehrere Posts teilen dieselbe topic_id"),
        ("2",  "forum_id",       "Forum-/Kategorie-ID (= Produkt-Modul)"),
        ("3",  "poster_id",      "Numerische Benutzer-ID des Autors"),
        ("4",  "icon_id",        "Post-Icon (immer 0 – nicht verwendet)"),
        ("5",  "poster_ip",      "IP-Adresse zum Zeitpunkt des Posts"),
        ("6",  "post_time",      "Veröffentlichungs-Zeitstempel (Unix, UTC)"),
        ("7",  "post_approved",  "Freigabe-Status (immer 1 = genehmigt)"),
        ("8",  "post_reported",  "Spam-Meldung (immer 0 = keine)"),
        ("9",  "enable_bbcode",  "BBCode aktiviert (immer 1)"),
        ("10", "enable_smilies", "Smileys aktiviert (meist 1)"),
        ("11", "enable_magic_url","Magic-URLs aktiviert (meist 1)"),
        ("12", "enable_sig",     "Signatur aktiviert (meist 1)"),
        ("13", "post_username",  "Gastname (nur bei anonymen Posts gefüllt)"),
        ("14", "post_subject",   "Betreff / Titel des Posts"),
        ("15", "post_text",      "Nachrichtentext (BBCode/HTML, mehrzeilig mögl.)"),
        ("16", "post_checksum",  "MD5-Prüfsumme des Textes"),
        ("17", "post_attachment","Hat Anhang: 0=nein, 1=ja"),
        ("18", "bbcode_bitfield","Base64-Bitfeld der verwendeten BBCode-Tags"),
        ("19", "bbcode_uid",     "BBCode-UID (eindeutig pro Post)"),
        ("20", "post_postcount", "Wird zum User-Postcount gezählt (meist 1)"),
        ("21", "post_edit_time", "Unix-TS der letzten Bearbeitung (0=nie)"),
        ("22", "post_edit_reason","Bearbeitungsgrund (immer leer)"),
        ("23", "post_edit_user", "Benutzer-ID des Bearbeiters"),
        ("24", "post_edit_count","Anzahl Bearbeitungen"),
        ("25", "post_edit_locked","Bearbeitung gesperrt (meist 0)"),
    ]
    lines.append(f"{'Sp':>3}  {'Feldname':<20}  Bedeutung")
    lines.append("-" * 68)
    for sp, name, desc in col_desc:
        lines.append(f"{sp:>3}  {name:<20}  {desc}")

    # ── 3. Zeitraum & Aktivität ─────────────────────────────────────────────
    h1("3. ZEITRAUM & AKTIVITÄT")
    timestamps = [int(r[COL["post_time"]]) for r in posts]
    dt_min = datetime.datetime.fromtimestamp(min(timestamps))
    dt_max = datetime.datetime.fromtimestamp(max(timestamps))
    lines.append(f"Ältester Post:  {dt_min:%d.%m.%Y %H:%M}")
    lines.append(f"Neuester Post:  {dt_max:%d.%m.%Y %H:%M}")
    lines.append(f"Zeitspanne:     {(dt_max - dt_min).days} Tage ({(dt_max - dt_min).days // 365} Jahre)")

    h2("Posts pro Jahr")
    years = Counter(datetime.datetime.fromtimestamp(int(r[COL["post_time"]])).year for r in posts)
    for y in sorted(years):
        bar = "█" * (years[y] // 10)
        lines.append(f"  {y}: {years[y]:>4}  {bar}")

    # ── 4. Foren / Kategorien ───────────────────────────────────────────────
    h1("4. FOREN / KATEGORIEN (forum_id)")
    forum_counts = Counter(r[COL["forum_id"]] for r in posts)
    lines.append(f"Anzahl distinct forum_id: {len(forum_counts)}")
    lines.append(f"\n{'forum_id':>10}  {'Posts':>6}  Beispiel-Titel")
    lines.append("-" * 68)
    for fid, cnt in forum_counts.most_common():
        example = next((r[COL["post_subject"]] for r in posts if r[COL["forum_id"]] == fid), "")
        lines.append(f"{fid:>10}  {cnt:>6}  {example[:45]}")

    # ── 5. Threads (Topics) ─────────────────────────────────────────────────
    h1("5. THREADS (topic_id)")
    topic_posts: dict[str, list] = defaultdict(list)
    for r in posts:
        topic_posts[r[COL["topic_id"]]].append(r)

    total_topics = len(topic_posts)
    multi = {k: v for k, v in topic_posts.items() if len(v) > 1}
    lines.append(f"Distinct topic_id:              {total_topics:>5}")
    lines.append(f"Threads mit > 1 Post:           {len(multi):>5}")
    lines.append(f"Threads mit genau 1 Post:       {total_topics - len(multi):>5}")
    avg = n / total_topics
    lines.append(f"Ø Posts pro Thread:             {avg:>7.2f}")

    top_threads = sorted(topic_posts.items(), key=lambda x: -len(x[1]))[:10]
    h2("Top-10 aktivste Threads")
    for tid, tposts in top_threads:
        title = tposts[0][COL["post_subject"]]
        lines.append(f"  topic_id={tid:>5}  {len(tposts):>3} Posts  {title[:45]}")

    # ── 6. Benutzer ─────────────────────────────────────────────────────────
    h1("6. BENUTZER")
    poster_ids = Counter(r[COL["poster_id"]] for r in posts)
    lines.append(f"Distinct poster_id:  {len(poster_ids):>5}")
    lines.append(f"Ø Posts pro Autor:   {n / len(poster_ids):>7.2f}")

    h2("Top-10 aktivste Autoren (poster_id)")
    for pid, cnt in poster_ids.most_common(10):
        lines.append(f"  poster_id={pid:>5}  {cnt:>4} Posts")

    guest_posts = sum(1 for r in posts if r[COL["post_username"]])
    lines.append(f"\nGast-Posts (post_username gesetzt): {guest_posts}")
    guest_names = Counter(r[COL["post_username"]] for r in posts if r[COL["post_username"]])
    if guest_names:
        lines.append("Gastnamen: " + ", ".join(f"{n} ({c}x)" for n, c in guest_names.most_common()))

    # ── 7. Bearbeitungen ────────────────────────────────────────────────────
    h1("7. BEARBEITUNGEN")
    edited = [r for r in posts if r[COL["post_edit_count"]] and r[COL["post_edit_count"]] != "0"]
    lines.append(f"Bearbeitete Posts:   {len(edited):>5}  ({len(edited)/n*100:.1f} %)")

    with_attach = [r for r in posts if r[COL["post_attachment"]] == "1"]
    lines.append(f"Posts mit Anhang:    {len(with_attach):>5}  ({len(with_attach)/n*100:.1f} %)")

    # ── 8. IP-Adressen ──────────────────────────────────────────────────────
    h1("8. IP-ADRESSEN (poster_ip)")
    ip_counts = Counter(r[COL["poster_ip"]] for r in posts)
    lines.append(f"Distinct IPs: {len(ip_counts)}")
    h2("Top-10 IPs nach Post-Anzahl")
    for ip, cnt in ip_counts.most_common(10):
        lines.append(f"  {ip:<20}  {cnt:>4} Posts")

    # ── 9. Text-Längen ──────────────────────────────────────────────────────
    h1("9. POST-TEXT-LÄNGEN")
    lengths = sorted(len(r[COL["post_text"]]) for r in posts)
    lines.append(f"Min. Länge:     {lengths[0]:>7} Zeichen")
    lines.append(f"Max. Länge:     {lengths[-1]:>7} Zeichen")
    lines.append(f"Median:         {lengths[n // 2]:>7} Zeichen")
    avg_len = sum(lengths) / n
    lines.append(f"Durchschnitt:   {avg_len:>9.1f} Zeichen")
    lines.append(f"Total Zeichen:  {sum(lengths):>7}")

    return "\n".join(lines)


def main() -> None:
    """Hauptfunktion: lädt Daten, erstellt Report, speichert Ergebnis."""
    logger.info("Lade %s", SOURCE)
    posts, total_raw = load_posts(SOURCE)
    logger.info("Gültige Posts: %d (von %d Zeilen)", len(posts), total_raw)

    report = generate_report(posts, total_raw)
    print(report)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    logger.info("Report gespeichert: %s", REPORT)


if __name__ == "__main__":
    main()
