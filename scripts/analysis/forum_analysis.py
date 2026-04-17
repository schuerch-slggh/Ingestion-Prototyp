"""Auswertung des SelectLine-Forum-Exports (Forum_Export_fixed.csv).

Analysiert die phpBB-Post-Tabelle und schreibt einen Report nach
data/eval/forum_report.txt.
"""

import csv
import datetime
import logging
import re
import statistics
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"

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


FORUM_NAMES: dict[str, str] = {
    "36": "SelectLine Auftrag Allgemein",
    "20": "Programmübergreifend",
    "12": "Neue Versionen",
    "15": "SelectLine Auftrag",
    "16": "SelectLine Lohn",
    "45": "SelectLine Rechnungswesen / Fibu Allgemein",
    "68": "Makros",
    "18": "SelectLine Mobile",
    "70": "CRM",
    "29": "PC-Kasse",
    "69": "Toolbox & COM",
    "19": "Plantafel",
    "83": "MDE",
    "57": "Skip5",
    "34": "Lagerverwaltung",
    "50": "SQL Server",
    "76": "Off-Topics - Partner-Lösungen",
    "24": "Installation / Updates",
    "85": "SelectLine Server",
    "26": "SQL Server",
    "78": "Programm Einrichtung",
    "82": "SelectLine News",
    "72": "Off-Topics - Partner-Lösungen",
    "49": "Kostenrechnung",
    "25": "Updates",
    "81": "Toolbox",
    "54": "Verbuchung der Bezugsteuer",
    "84": "Doqio",
    "80": "OPOS EZV Rechnungswesen",
    "77": "Fremdwährungen im Kassabuch",
    "27": "Abkündigung SQL Server 2008 R2 und Windows Vi",
    "74": "SelectLine stellt sich vor - Rundgang durch's",
    "17": "V17 USTVADAT keine Anzeige - Lösung",
    "59": "Allgemeine Forum Regel für die Registrierung",
    "79": "Einrichtung Lohn",
    "56": "ELM: EIV-Upload der XML-Datei per Internet",
}

_RE_REPLY_PREFIX = re.compile(r"^(re\s*:\s*)+", re.IGNORECASE)
# Mojibake patterns: U+FFFD, â€-sequences, Ã followed by a non-space character
_RE_ENCODING = re.compile(r"\ufffd|â€|Ã\S")


def _word_count(text: str) -> int:
    """Zählt Wörter anhand von Whitespace-Trennung."""
    return len(text.split())


def _is_uninformative_subject(subject: str) -> bool:
    """True wenn Betreff leer, reines Re:-Präfix oder < 3 Zeichen nach Bereinigung."""
    s = subject.strip()
    if not s:
        return True
    return len(_RE_REPLY_PREFIX.sub("", s).strip()) < 3


def generate_report(posts: list[list[str]], total_raw: int) -> str:
    """Erstellt den Auswertungs-Report als String."""
    lines: list[str] = []
    n = len(posts)

    def h1(title: str) -> None:
        lines.append("\n" + "=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def h2(title: str) -> None:
        lines.append(f"\n--- {title} ---")

    def pct(count: int) -> str:
        return f"{count / n * 100:.1f} %" if n else "n/a"

    # ── Kopf ────────────────────────────────────────────────────────────────
    lines.append("FORUM-EXPORT AUSWERTUNG – SelectLine Community Forum")
    lines.append(f"Erstellt: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Quelldatei: {SOURCE.name}")

    # ── 1. Umfang ───────────────────────────────────────────────────────────
    h1("1. UMFANG")
    lines.append(f"Anzahl Datensätze (gültige Posts):  {n:>7}")

    valid_ts = [
        int(r[COL["post_time"]])
        for r in posts
        if r[COL["post_time"]].strip().lstrip("-").isdigit()
        and int(r[COL["post_time"]]) > 0
    ]
    if valid_ts:
        dt_min = datetime.datetime.fromtimestamp(min(valid_ts))
        dt_max = datetime.datetime.fromtimestamp(max(valid_ts))
        span = dt_max - dt_min
        lines.append(f"Ältester Beitrag:                   {dt_min:%d.%m.%Y %H:%M}")
        lines.append(f"Neuester Beitrag:                   {dt_max:%d.%m.%Y %H:%M}")
        lines.append(
            f"Zeitspanne:                         "
            f"{span.days} Tage  ({span.days // 365} Jahre)"
        )
    else:
        lines.append("Zeitraum: keine gültigen Timestamps vorhanden")

    # ── 2. Vollständigkeit und Missing Values ───────────────────────────────
    h1("2. VOLLSTÄNDIGKEIT UND MISSING VALUES")

    no_content = sum(
        1
        for r in posts
        if not r[COL["post_text"]].strip() or not r[COL["post_subject"]].strip()
    )
    lines.append(
        f"Ohne post_text oder post_subject:   "
        f"{no_content:>6}  ({pct(no_content)})"
    )

    no_forum = sum(1 for r in posts if not r[COL["forum_id"]].strip())
    lines.append(f"Ohne forum_id:                      {no_forum:>6}  ({pct(no_forum)})")

    no_time = sum(
        1
        for r in posts
        if not r[COL["post_time"]].strip() or r[COL["post_time"]].strip() == "0"
    )
    lines.append(f"Ohne post_time:                     {no_time:>6}  ({pct(no_time)})")

    # ── 3. Inhaltsqualität der Beiträge ────────────────────────────────────
    h1("3. INHALTSQUALITÄT DER BEITRÄGE")

    # Duplikate
    post_ids = [r[COL["post_id"]] for r in posts]
    dup_ids = len(post_ids) - len(set(post_ids))
    lines.append(f"Doppelte post_id:                   {dup_ids:>6}  ({pct(dup_ids)})")

    post_subjects = [r[COL["post_subject"]].strip() for r in posts]
    dup_subjects = len(post_subjects) - len(set(post_subjects))
    lines.append(
        f"Doppelte post_subject:              {dup_subjects:>6}  ({pct(dup_subjects)})"
    )

    subject_text_pairs = [
        (r[COL["post_subject"]].strip(), r[COL["post_text"]].strip()) for r in posts
    ]
    dup_pairs = len(subject_text_pairs) - len(set(subject_text_pairs))
    lines.append(
        f"Identische subject+text (Duplikate):{dup_pairs:>6}  ({pct(dup_pairs)})"
    )

    post_texts = [r[COL["post_text"]].strip() for r in posts]
    dup_texts = len(post_texts) - len(set(post_texts))
    lines.append(
        f"Doppelte post_text:                 {dup_texts:>6}  ({pct(dup_texts)})"
    )

    # Textlängen in Zeichen
    h2("Textlänge (Zeichen, post_text)")
    char_lengths = sorted(len(r[COL["post_text"]]) for r in posts)
    avg_chars = sum(char_lengths) / n
    med_chars = statistics.median(char_lengths)
    lines.append(f"  Durchschnitt:  {avg_chars:>8.1f}")
    lines.append(f"  Minimum:       {char_lengths[0]:>8}")
    lines.append(f"  Median:        {med_chars:>8.1f}")
    lines.append(f"  Maximum:       {char_lengths[-1]:>8}")

    # Wortanzahl-basierte Kriterien
    word_counts = [_word_count(r[COL["post_text"]]) for r in posts]
    short_posts = sum(1 for wc in word_counts if wc < 30)
    long_posts = sum(1 for wc in word_counts if wc > 100)
    lines.append(
        f"\nSehr kurze Beiträge (< 30 Wörter):  {short_posts:>6}  ({pct(short_posts)})"
    )
    lines.append(
        f"Sehr lange Beiträge (> 100 Wörter): {long_posts:>6}  ({pct(long_posts)})"
    )

    # Aussagekräftigkeit des Betreffs
    uninformative = sum(
        1 for r in posts if _is_uninformative_subject(r[COL["post_subject"]])
    )
    lines.append(
        f"\nBeiträge ohne aussagekräftigen Betreff:"
        f"  {uninformative:>6}  ({pct(uninformative)})"
    )
    lines.append(
        "  (leer, reines Re:-Präfix, oder < 3 Zeichen nach Bereinigung)"
    )

    # Encoding-Fehler
    enc_errors = sum(
        1
        for r in posts
        if _RE_ENCODING.search(r[COL["post_text"]])
        or _RE_ENCODING.search(r[COL["post_subject"]])
    )
    lines.append(
        f"Beiträge mit Encoding-Fehlern:      {enc_errors:>6}  ({pct(enc_errors)})"
    )
    lines.append(
        "  (U+FFFD, â€…-Sequenzen, Ã-Mojibake in post_text oder post_subject)"
    )

    # ── 4. Informationsverteilung ───────────────────────────────────────────
    h1("4. INFORMATIONSVERTEILUNG")
    h2("Verteilung der Beiträge pro Produkt / Forum")
    forum_counts = Counter(r[COL["forum_id"]] for r in posts)
    lines.append(f"Distinct Produkte / Foren: {len(forum_counts)}")
    lines.append(f"\n{'Produkt / Forum':<46}  {'Anzahl':>7}  {'Anteil':>8}")
    lines.append("-" * 66)
    for fid, cnt in forum_counts.most_common():
        name = FORUM_NAMES.get(fid, f"forum_id {fid}")
        lines.append(f"{name:<46}  {cnt:>7}  {cnt / n * 100:>7.1f} %")

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
