"""Ticket-Datenaufbereitung: Bronze → Silver → Gold."""

import html as html_module
import logging
import re
from pathlib import Path

import pandas as pd

from rag.config import RANDOM_SEED
from rag.preparation.dbf_reader import read_dbf
from rag.preparation.lookups import resolve_product, resolve_ticket_status

logger = logging.getLogger(__name__)

_BRONZE_COLS = [
    "ID", "KATEGORIE", "VERSION", "VERSIONERL",
    "BESCHREIBU", "PRODUKTID", "FEHLER", "LOESUNG", "STATUSID", "BEARBEITET",
]

_RE_HTML = re.compile(r"<[^>]+>")
_RE_MULTI_SPACE = re.compile(r"[ \t]+")
_RE_MULTI_NEWLINE = re.compile(r"\n{2,}")

# Signatur-Trennzeichen: Zeilen, die eine E-Mail-Signatur einleiten
_SIGNATURE_PATTERNS = re.compile(
    r"\n--\s*\n.*$"
    r"|\nMit freundlichen Gr[uü]ssen.*$"
    r"|\nMit freundlichen Gr[uü]ßen.*$"
    r"|\nBest regards.*$"
    r"|\nKind regards.*$"
    r"|\nFreundliche Gr[uü]sse.*$",
    re.IGNORECASE | re.DOTALL,
)


def load_bronze(
    dbf_path: Path,
    dbt_path: Path,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """Lädt die Bronze-Ticket-DBF und filtert auf die zehn relevanten Spalten.

    Args:
        dbf_path: Pfad zur vorgaenge.dbf.
        dbt_path: Pfad zur vorgaenge.dbt (Memo-Datei).
        sample_size: Bei Angabe reproduzierbare Stichprobe dieser Größe.

    Returns:
        DataFrame mit den Spalten ID, KATEGORIE, VERSION, VERSIONERL,
        BESCHREIBU, PRODUKTID, FEHLER, LOESUNG, STATUSID, BEARBEITET.
    """
    df, stats = read_dbf(dbf_path, dbt_path)

    missing = [c for c in _BRONZE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Fehlende Spalten in DBF: {missing}")

    df = df[_BRONZE_COLS].copy()

    if sample_size is not None:
        df = df.sample(n=min(sample_size, len(df)), random_state=RANDOM_SEED)

    logger.info(
        "Bronze geladen: %d Tickets (%d Records total, %d gelöscht)",
        len(df),
        stats["records_total"],
        stats["records_deleted"],
    )
    return df.reset_index(drop=True)


def _normalize_whitespace(text: str) -> str:
    """Normalisiert mehrfache Leerzeichen und Zeilenumbrüche."""
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = _RE_MULTI_NEWLINE.sub("\n", text)
    return text.strip()


def _remove_signature(text: str) -> str:
    """Entfernt E-Mail-Signaturen aus Memo-Feldern."""
    return _SIGNATURE_PATTERNS.sub("", text).strip()


def _clean_text(text: str) -> str:
    """Entfernt HTML-Tags und HTML-Entities, normalisiert Whitespace."""
    text = _RE_HTML.sub("", text)
    text = html_module.unescape(text)
    return _normalize_whitespace(text)


def clean_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Bereinigt Bronze-Daten zu Silver.

    - Whitespace normalisieren in allen Textfeldern
    - E-Mail-Signaturen aus FEHLER und LOESUNG entfernen
    - HTML-Tags und HTML-Entities in FEHLER und LOESUNG entfernen
    - PRODUKTID → Spalte product (aufgelöst via resolve_product)
    - STATUSID → Spalte status (aufgelöst via resolve_ticket_status)
    - BEARBEITET → processed_date
    - Filter: Tickets mit leerem LOESUNG verwerfen
    - Logging: Anzahl vor/nach Filter, Signaturen, Whitespace

    Returns:
        DataFrame mit Spalten: ID, KATEGORIE, VERSION, VERSIONERL,
        BESCHREIBU, product, FEHLER, LOESUNG, status, processed_date.
    """
    df = df.copy()

    text_cols = ["ID", "KATEGORIE", "VERSION", "VERSIONERL", "BESCHREIBU",
                 "FEHLER", "LOESUNG"]
    ws_count = 0
    for col in text_cols:
        df[col] = df[col].fillna("")
        original = df[col].copy()
        df[col] = df[col].apply(_normalize_whitespace)
        ws_count += int((df[col] != original).sum())
    logger.info("Whitespace normalisiert: %d Felder geändert", ws_count)

    sig_count = 0
    for col in ("FEHLER", "LOESUNG"):
        original = df[col].copy()
        df[col] = df[col].apply(_remove_signature)
        sig_count += int((df[col] != original).sum())
    logger.info("Signaturen entfernt: %d Felder bereinigt", sig_count)

    html_count = 0
    for col in ("FEHLER", "LOESUNG"):
        original = df[col].copy()
        df[col] = df[col].apply(_clean_text)
        html_count += int((df[col] != original).sum())
    logger.info("HTML/Entities bereinigt: %d Felder geändert", html_count)

    df["product"] = df["PRODUKTID"].apply(resolve_product)
    df["status"] = df["STATUSID"].apply(resolve_ticket_status)
    df = df.rename(columns={"BEARBEITET": "processed_date"})
    df = df.drop(columns=["PRODUKTID", "STATUSID"])

    before = len(df)
    df = df[df["LOESUNG"].str.strip() != ""]
    after = len(df)
    logger.info(
        "Tickets nach Leerungs-Filter: %d → %d (entfernt: %d)",
        before, after, before - after,
    )

    col_order = [
        "ID", "KATEGORIE", "VERSION", "VERSIONERL", "BESCHREIBU",
        "product", "FEHLER", "LOESUNG", "status", "processed_date",
    ]
    return df[col_order].reset_index(drop=True)


def transform_to_gold(df: pd.DataFrame) -> list[dict]:
    """Überführt Silver-Daten in das Gold-JSONL-Format.

    Kombiniert Beschreibung, Fehlerbeschreibung und Lösung im full_text,
    damit das Embedding den vollständigen Kontext eines Tickets erfasst.
    """
    records = []
    for _, row in df.iterrows():
        full_text = (
            f"{row['BESCHREIBU']}\n\n"
            f"Fehlerbeschreibung:\n{row['FEHLER']}\n\n"
            f"Lösung:\n{row['LOESUNG']}"
        )
        records.append({
            "doc_id": f"ticket_{row['ID']}",
            "source_type": "ticket",
            "metadata": {
                "ticket_id": str(row["ID"]),
                "category": str(row["KATEGORIE"]),
                "version_reported": str(row["VERSION"]),
                "version_resolved": str(row["VERSIONERL"]),
                "product": str(row["product"]),
                "status": str(row["status"]),
                "processed_date": str(row["processed_date"]),
                "title": str(row["BESCHREIBU"]),
            },
            "content": {"full_text": full_text},
        })
    logger.info("Gold-Records erstellt: %d", len(records))
    return records
