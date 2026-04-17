"""Konvertiert vorgaenge.dbf + vorgaenge.dbt → data/interim/vorgaenge.csv.

Liest die dBASE-III+-Datei ohne externe Bibliotheken (pure Python).

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

import csv
import logging
import struct
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE: Path = PROJECT_ROOT / "data" / "raw" / "vorgaenge.dbf"
DBT: Path = PROJECT_ROOT / "data" / "raw" / "vorgaenge.dbt"
TARGET: Path = PROJECT_ROOT / "data" / "interim" / "vorgaenge.csv"

ENCODING = "cp850"   # DOS-Westeuropa; bestätigt durch Umlaut-Prüfung
DBT_BLOCK_SIZE = 512  # dBASE III .DBT: feste 512-Byte-Blöcke


# ---------------------------------------------------------------------------
# DBT-Memo-Lesehilfe
# ---------------------------------------------------------------------------

def _read_memo(dbt_file, block_num: int) -> str:
    """Liest einen Memo-Eintrag aus der .DBT-Datei.

    dBASE-III-.DBT: Block 0 ist der Header (512 Bytes). Nutzdaten starten
    bei block_num * 512. Der Inhalt endet beim ersten 0x1A-Byte (Ctrl-Z).

    Args:
        dbt_file: Geöffnetes binäres Datei-Handle der .DBT-Datei.
        block_num: Blocknummer (aus dem Memo-Referenzfeld der DBF).

    Returns:
        Dekodierter Text oder leerer String bei ungültiger Referenz.
    """
    if block_num <= 0:
        return ""
    dbt_file.seek(block_num * DBT_BLOCK_SIZE)
    chunks: list[bytes] = []
    while True:
        chunk = dbt_file.read(DBT_BLOCK_SIZE)
        if not chunk:
            break
        end = chunk.find(b"\x1a")
        if end != -1:
            chunks.append(chunk[:end])
            break
        chunks.append(chunk)
    raw = b"".join(chunks)
    return raw.decode(ENCODING, errors="replace")


# ---------------------------------------------------------------------------
# DBF-Lesehilfen
# ---------------------------------------------------------------------------

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
    """Dekodiert einen Feldwert in einen CSV-tauglichen String."""
    text = raw.decode(ENCODING, errors="replace")

    if ftype == "C":
        return text.rstrip()

    if ftype == "N":
        stripped = text.strip()
        if not stripped:
            return ""
        # Integer wenn kein Dezimalpunkt
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

    # Fallback: roher String
    return text.rstrip()


# ---------------------------------------------------------------------------
# Hauptkonvertierung
# ---------------------------------------------------------------------------

def convert(source: Path, dbt: Path, target: Path) -> None:
    """Liest *source* (DBF) + *dbt* (.DBT) und schreibt *target* (CSV, UTF-8)."""
    logger.info("Öffne %s", source)
    dbt_file = None
    if dbt.exists():
        logger.info("Öffne Memo-Datei %s", dbt)
        dbt_file = open(dbt, "rb")
    else:
        logger.warning("Memo-Datei nicht gefunden: %s – Memo-Felder bleiben leer.", dbt)

    try:
        with open(source, "rb") as f:
            num_records, header_size, record_size = _read_header(f)
            fields = _read_field_descriptors(f)
            f.seek(header_size)

            memo_fields = [n for n, t, _ in fields if t == "M"]
            if memo_fields and dbt_file:
                logger.info("Memo-Felder werden aus .DBT gelesen: %s", ", ".join(memo_fields))
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

            target.parent.mkdir(parents=True, exist_ok=True)
            skipped_deleted = 0
            written = 0

            with open(target, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
                writer.writerow([name for name, _, _ in fields])

                for _ in range(num_records):
                    record_raw = f.read(record_size)
                    if len(record_raw) < record_size:
                        logger.warning("Unerwartetes Ende der Datei.")
                        break

                    # Deletion-Flag: 0x2A = '*' bedeutet gelöscht
                    if record_raw[0] == 0x2A:
                        skipped_deleted += 1
                        continue

                    row: list[str] = []
                    offset = 1  # Byte 0 ist das Deletion-Flag
                    for name, ftype, flen in fields:
                        raw = record_raw[offset : offset + flen]
                        row.append(_decode_field(raw, ftype, name, dbt_file))
                        offset += flen

                    writer.writerow(row)
                    written += 1
    finally:
        if dbt_file:
            dbt_file.close()

    logger.info(
        "Fertig: %d Records geschrieben, %d gelöschte Records übersprungen.",
        written,
        skipped_deleted,
    )
    logger.info("CSV gespeichert: %s", target)


def main() -> None:
    convert(SOURCE, DBT, TARGET)


if __name__ == "__main__":
    main()
