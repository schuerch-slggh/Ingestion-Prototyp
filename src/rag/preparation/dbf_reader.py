"""Liest dBASE-III+-Dateien (DBF + optional DBT) in einen pandas DataFrame.

Unterstützte Feldtypen
-----------------------
C  Character  – rechts getrimmter String, Encoding cp850
N  Numeric    – Ganzzahl oder Float (leer → leerer String)
D  Date       – YYYYMMDD → ISO-Format YYYY-MM-DD (leer → leerer String)
L  Logical    – T/Y → True, F/N → False, Leerzeichen → leerer String
M  Memo       – aus begleitender .DBT-Datei (dBASE III, 512-Byte-Blöcke,
               Inhalt endet bei 0x1A-Byte), Encoding cp850.

Gelöschte Records (Deletion-Flag = '*') werden übersprungen.
"""

import logging
import struct
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_ENCODING = "cp850"
_DBT_BLOCK_SIZE = 512


def _read_memo(dbt_file, block_num: int) -> str:
    """Liest einen Memo-Eintrag aus der .DBT-Datei."""
    if block_num <= 0:
        return ""
    dbt_file.seek(block_num * _DBT_BLOCK_SIZE)
    chunks: list[bytes] = []
    while True:
        chunk = dbt_file.read(_DBT_BLOCK_SIZE)
        if not chunk:
            break
        end = chunk.find(b"\x1a")
        if end != -1:
            chunks.append(chunk[:end])
            break
        chunks.append(chunk)
    raw = b"".join(chunks)
    return raw.decode(_ENCODING, errors="replace")


def _read_header(f) -> tuple[int, int, int]:
    """Liest die 32-Byte-DBF-Kopfzeile.

    Returns:
        (num_records, header_size, record_size)
    """
    raw = f.read(32)
    num_records = struct.unpack("<I", raw[4:8])[0]
    header_size = struct.unpack("<H", raw[8:10])[0]
    record_size = struct.unpack("<H", raw[10:12])[0]
    return num_records, header_size, record_size


def _read_field_descriptors(f) -> list[tuple[str, str, int]]:
    """Liest alle 32-Byte-Felddeskriptoren bis zum Terminierungsbyte 0x0D.

    Returns:
        Liste von (feldname, typ, länge).
    """
    fields: list[tuple[str, str, int]] = []
    while True:
        desc = f.read(32)
        if not desc or desc[0] == 0x0D:
            break
        name = desc[0:11].replace(b"\x00", b"").decode("ascii")
        ftype = chr(desc[11])
        flen = desc[16]
        fields.append((name, ftype, flen))
    return fields


def _decode_field(raw: bytes, ftype: str, name: str, dbt_file=None) -> str:
    """Dekodiert einen Feldwert in einen String."""
    text = raw.decode(_ENCODING, errors="replace")

    if ftype == "C":
        return text.rstrip()

    if ftype == "N":
        stripped = text.strip()
        if not stripped:
            return ""
        if "." not in stripped:
            try:
                return str(int(stripped))
            except ValueError:
                return stripped
        try:
            return str(float(stripped))
        except ValueError:
            return stripped

    if ftype == "D":
        stripped = text.strip()
        if len(stripped) == 8 and stripped.isdigit():
            return f"{stripped[:4]}-{stripped[4:6]}-{stripped[6:8]}"
        return ""

    if ftype == "L":
        ch = text.strip().upper()
        if ch in ("T", "Y"):
            return "True"
        if ch in ("F", "N"):
            return "False"
        return ""

    if ftype == "M":
        if dbt_file is None:
            return ""
        block_ref = text.strip()
        if not block_ref:
            return ""
        try:
            block_num = int(block_ref)
        except ValueError:
            return ""
        return _read_memo(dbt_file, block_num)

    return text.rstrip()


def read_dbf(dbf_path: Path, dbt_path: Path) -> tuple[pd.DataFrame, dict]:
    """Liest eine DBF + DBT in einen pandas DataFrame.

    Args:
        dbf_path: Pfad zur DBF-Datei.
        dbt_path: Pfad zur DBT-Memo-Datei. Wenn nicht vorhanden,
                  bleiben Memo-Felder leer (Warnung wird geloggt).

    Returns:
        Tuple aus:
        - DataFrame mit allen aktiven Records, alle Felder als String,
          Encoding cp850 → UTF-8 dekodiert
        - Statistik-Dict: {
              "records_total": int,
              "records_loaded": int,
              "records_deleted": int,
              "fields": list[str],
          }
    """
    logger.info("Öffne %s", dbf_path)
    dbt_file = None
    if dbt_path.exists():
        logger.info("Öffne Memo-Datei %s", dbt_path)
        dbt_file = open(dbt_path, "rb")  # noqa: SIM115
    else:
        logger.warning(
            "Memo-Datei nicht gefunden: %s – Memo-Felder bleiben leer.", dbt_path
        )

    rows: list[list[str]] = []
    field_names: list[str] = []
    records_deleted = 0

    try:
        with open(dbf_path, "rb") as f:
            num_records, header_size, record_size = _read_header(f)
            fields = _read_field_descriptors(f)
            field_names = [name for name, _, _ in fields]
            f.seek(header_size)

            memo_fields = [n for n, t, _ in fields if t == "M"]
            if memo_fields and dbt_file:
                logger.info(
                    "Memo-Felder werden aus .DBT gelesen: %s", ", ".join(memo_fields)
                )
            elif memo_fields:
                logger.warning(
                    "Memo-Felder ohne Inhalt (keine .DBT-Datei): %s",
                    ", ".join(memo_fields),
                )

            logger.info(
                "Struktur: %d Records, %d Felder, Record-Größe %d Bytes",
                num_records,
                len(fields),
                record_size,
            )

            for _ in range(num_records):
                record_raw = f.read(record_size)
                if len(record_raw) < record_size:
                    logger.warning("Unerwartetes Ende der Datei.")
                    break

                if record_raw[0] == 0x2A:  # Deletion-Flag '*'
                    records_deleted += 1
                    continue

                row: list[str] = []
                offset = 1
                for name, ftype, flen in fields:
                    raw = record_raw[offset : offset + flen]
                    row.append(_decode_field(raw, ftype, name, dbt_file))
                    offset += flen
                rows.append(row)
    finally:
        if dbt_file:
            dbt_file.close()

    records_loaded = len(rows)
    logger.info(
        "Fertig: %d Records geladen, %d gelöschte Records übersprungen.",
        records_loaded,
        records_deleted,
    )

    df = pd.DataFrame(rows, columns=field_names)
    stats = {
        "records_total": records_loaded + records_deleted,
        "records_loaded": records_loaded,
        "records_deleted": records_deleted,
        "fields": field_names,
    }
    return df, stats
