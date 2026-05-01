"""Tests für die Ticket-Datenaufbereitung (AP-2b)."""

import struct
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from rag.preparation.dbf_reader import read_dbf
from rag.preparation.tickets import (
    clean_to_silver,
    load_bronze,
    transform_to_gold,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen für synthetische Testdaten
# ---------------------------------------------------------------------------


def _make_dbf_bytes(rows: list[tuple[bool, str]]) -> bytes:
    """Erstellt eine minimale DBF-III-Binärstruktur mit einem C-Feld 'NAME' (Länge 10).

    Args:
        rows: Liste von (is_deleted, name_value) Tupeln.
    """
    # Felddeskriptor für NAME (32 Bytes)
    field_desc = (
        b"NAME\x00\x00\x00\x00\x00\x00\x00"  # Feldname (11 Bytes, nullpadded)
        + b"C"                                  # Typ
        + b"\x00\x00\x00\x00"                  # reserviert
        + bytes([10])                            # Länge
        + b"\x00" * 15                          # reserviert
    )

    num_records = len(rows)
    header_size = 32 + 32 + 1   # DBF-Header + 1 Felddeskriptor + Terminator
    record_size = 1 + 10        # Deletion-Flag + NAME-Feld

    header = struct.pack(
        "<B3sIHH20s",
        0x03,             # Version dBASE III
        b"\x1a\x05\x01",  # Datum (Jahr/Monat/Tag, nicht relevant für Tests)
        num_records,
        header_size,
        record_size,
        b"\x00" * 20,     # reserviert
    )

    records = b""
    for is_deleted, name in rows:
        flag = b"\x2a" if is_deleted else b"\x20"
        data = name.encode("cp850").ljust(10, b" ")[:10]
        records += flag + data

    return header + field_desc + b"\x0d" + records


def _make_bronze_df(n: int = 3, with_loesung: bool = True) -> pd.DataFrame:
    """Erstellt einen minimalen Bronze-DataFrame für clean_to_silver-Tests."""
    return pd.DataFrame({
        "ID": [str(i) for i in range(1, n + 1)],
        "KATEGORIE": ["Fehler"] * n,
        "VERSION": ["24.1"] * n,
        "VERSIONERL": ["24.2"] * n,
        "BESCHREIBU": [f"Ticket {i}" for i in range(1, n + 1)],
        "PRODUKTID": ["1"] * n,
        "FEHLER": [f"Fehlerbeschreibung {i}" for i in range(1, n + 1)],
        "LOESUNG": [f"Lösung {i}" if with_loesung else "" for i in range(1, n + 1)],
        "STATUSID": ["1000"] * n,
        "BEARBEITET": ["2024-01-15"] * n,
    })


def _make_silver_df(n: int = 3) -> pd.DataFrame:
    """Erstellt einen minimalen Silver-DataFrame für transform_to_gold-Tests."""
    return pd.DataFrame({
        "ID": [str(i) for i in range(1, n + 1)],
        "KATEGORIE": ["Fehler"] * n,
        "VERSION": ["24.1"] * n,
        "VERSIONERL": ["24.2"] * n,
        "BESCHREIBU": [f"Ticket {i}" for i in range(1, n + 1)],
        "product": ["Auftrag"] * n,
        "FEHLER": [f"Fehlerbeschreibung {i}" for i in range(1, n + 1)],
        "LOESUNG": [f"Lösung {i}" for i in range(1, n + 1)],
        "status": ["Erledigt"] * n,
        "processed_date": ["2024-01-15"] * n,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_read_dbf_skips_deleted_records(tmp_path: Path) -> None:
    """Gelöschte Records (Deletion-Flag 0x2A) dürfen nicht im DataFrame landen."""
    dbf_path = tmp_path / "test.dbf"
    dbt_path = tmp_path / "test.dbt"  # existiert nicht → Memo-Felder bleiben leer
    dbf_bytes = _make_dbf_bytes([
        (False, "Alice"),
        (True, "Bob"),
        (False, "Charlie"),
    ])
    dbf_path.write_bytes(dbf_bytes)

    df, stats = read_dbf(dbf_path, dbt_path)

    assert len(df) == 2, "Nur 2 aktive Records erwartet"
    assert stats["records_deleted"] == 1
    assert stats["records_loaded"] == 2
    assert stats["records_total"] == 3
    assert "Alice" in df["NAME"].values
    assert "Charlie" in df["NAME"].values
    assert "Bob" not in df["NAME"].values


def test_load_bronze_filters_columns(tmp_path: Path) -> None:
    """load_bronze darf nur die zehn definierten Spalten zurückgeben."""
    all_cols = [
        "ID", "KATEGORIE", "VERSION", "VERSIONERL", "BESCHREIBU",
        "PRODUKTID", "FEHLER", "LOESUNG", "STATUSID", "BEARBEITET",
        "EXTRA_FELD_A", "EXTRA_FELD_B",
    ]
    dummy_df = pd.DataFrame([["v"] * len(all_cols)], columns=all_cols)
    fake_stats = {
        "records_total": 1, "records_loaded": 1,
        "records_deleted": 0, "fields": all_cols,
    }
    with patch("rag.preparation.tickets.read_dbf", return_value=(dummy_df, fake_stats)):
        result = load_bronze(tmp_path / "x.dbf", tmp_path / "x.dbt")

    expected_cols = [
        "ID", "KATEGORIE", "VERSION", "VERSIONERL", "BESCHREIBU",
        "PRODUKTID", "FEHLER", "LOESUNG", "STATUSID", "BEARBEITET",
    ]
    assert list(result.columns) == expected_cols


def test_clean_to_silver_resolves_codes() -> None:
    """Bekannte PRODUKTID- und STATUSID-Codes müssen in Klartext aufgelöst werden."""
    df = pd.DataFrame({
        "ID": ["1", "2", "3"],
        "KATEGORIE": ["A", "B", "C"],
        "VERSION": ["1.0", "1.0", "1.0"],
        "VERSIONERL": ["1.1", "1.1", "1.1"],
        "BESCHREIBU": ["T1", "T2", "T3"],
        "PRODUKTID": ["1", "2", "999"],
        "FEHLER": ["F1", "F2", "F3"],
        "LOESUNG": ["L1", "L2", "L3"],
        "STATUSID": ["1000", "7", "999"],
        "BEARBEITET": ["2024-01-01", "2024-01-02", "2024-01-03"],
    })
    result = clean_to_silver(df)

    assert result.loc[0, "product"] == "Auftrag"        # PRODUKTID 1 bekannt
    assert result.loc[1, "product"] == "Rechnungswesen"  # PRODUKTID 2 bekannt
    assert result.loc[2, "product"] == "999"             # PRODUKTID 999 unbekannt → Code

    assert result.loc[0, "status"] == "Erledigt"         # STATUSID 1000 bekannt
    assert result.loc[1, "status"] == "Zu Bearbeiten"    # STATUSID 7 bekannt
    assert result.loc[2, "status"] == "999"              # STATUSID 999 unbekannt → Code

    # Originale Codespalten dürfen nicht mehr vorhanden sein
    assert "PRODUKTID" not in result.columns
    assert "STATUSID" not in result.columns
    assert "BEARBEITET" not in result.columns
    assert "processed_date" in result.columns


def test_clean_to_silver_filters_empty_loesung() -> None:
    """Tickets mit leerem LOESUNG-Feld nach Bereinigung müssen verworfen werden."""
    df = pd.DataFrame({
        "ID": ["1", "2", "3"],
        "KATEGORIE": ["A", "B", "C"],
        "VERSION": ["1.0", "1.0", "1.0"],
        "VERSIONERL": ["1.1", "1.1", "1.1"],
        "BESCHREIBU": ["T1", "T2", "T3"],
        "PRODUKTID": ["1", "1", "1"],
        "FEHLER": ["F1", "F2", "F3"],
        "LOESUNG": ["Lösung vorhanden", "", "   "],  # nur ID 1 hat Lösung
        "STATUSID": ["1000", "1000", "1000"],
        "BEARBEITET": ["2024-01-01", "2024-01-02", "2024-01-03"],
    })
    result = clean_to_silver(df)

    assert len(result) == 1
    assert result.iloc[0]["ID"] == "1"


def test_transform_to_gold_produces_correct_schema() -> None:
    """Gold-Records müssen dem definierten Schema entsprechen."""
    df = _make_silver_df(3)
    records = transform_to_gold(df)

    assert len(records) == 3
    for i, record in enumerate(records, start=1):
        assert record["doc_id"] == f"ticket_{i}"
        assert record["source_type"] == "ticket"

        meta = record["metadata"]
        for key in ("ticket_id", "category", "version_reported",
                    "version_resolved", "product", "status",
                    "processed_date", "title"):
            assert key in meta, f"Metadaten-Key '{key}' fehlt in Record {i}"

        full_text = record["content"]["full_text"]
        assert "Fehlerbeschreibung:" in full_text, "Marker 'Fehlerbeschreibung:' fehlt"
        assert "Lösung:" in full_text, "Marker 'Lösung:' fehlt"
        assert f"Ticket {i}" in full_text, f"Titel fehlt in full_text von Record {i}"
