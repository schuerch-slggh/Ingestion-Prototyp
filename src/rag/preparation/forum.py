"""Forum-Datenaufbereitung: Bronze → Silver → Gold."""

import html as html_module
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from rag.config import RANDOM_SEED
from rag.preparation.lookups import resolve_forum_module

logger = logging.getLogger(__name__)

# Spaltenindizes im phpBB phpbb_posts-Export (26 Spalten gesamt)
_BRONZE_USECOLS = [0, 1, 2, 6, 14, 15]
_BRONZE_NAMES = [
    "post_id", "topic_id", "forum_id", "post_time", "post_subject", "post_text"
]

# Regex-Muster (String-Form für pandas .str.contains, compiled für .sub)
_HTML_PATTERN = r"<[^>]+>"
_BBCODE_PATTERN = r"\[/?[a-zA-Z][^\]]*\]"
_RE_HTML = re.compile(_HTML_PATTERN)
_RE_BBCODE = re.compile(_BBCODE_PATTERN)
_RE_SPACES = re.compile(r"[ \t]+")
_RE_NEWLINES = re.compile(r"\n+")


def load_bronze(
    source_path: Path, sample_size: int | None = None
) -> pd.DataFrame:
    """Lädt die Bronze-Forum-CSV mit inline Encoding-Korrektur.

    Wendet Latin-1→UTF-8 Mojibake-Fix an, selektiert die sechs
    relevanten Spalten und gibt bei sample_size eine reproduzierbare
    Stichprobe zurück.
    """
    raw_text = source_path.read_text(encoding="latin-1")
    fixed_text = raw_text.encode("latin-1").decode("utf-8")

    df = pd.read_csv(
        io.StringIO(fixed_text),
        sep=";",
        header=None,
        dtype=str,
        on_bad_lines="skip",
    )

    df = df.iloc[:, _BRONZE_USECOLS].copy()
    df.columns = _BRONZE_NAMES  # type: ignore[assignment]

    # Artefakt-Zeilen aus unquotierten mehrzeiligen Feldern herausfiltern
    df = df[df["post_id"].str.match(r"^\d+$", na=False)]

    df["post_time"] = (
        pd.to_numeric(df["post_time"], errors="coerce").fillna(0).astype(int)
    )

    if sample_size is not None:
        df = df.sample(n=min(sample_size, len(df)), random_state=RANDOM_SEED)

    logger.info("Bronze geladen: %d Beiträge aus %s", len(df), source_path.name)
    return df.reset_index(drop=True)


def _clean_markup(text: str) -> str:
    """Entfernt HTML-Tags, HTML-Entities, BBCode-Tags; normalisiert Whitespace."""
    text = _RE_HTML.sub("", text)
    text = html_module.unescape(text)
    text = _RE_BBCODE.sub("", text)
    text = _RE_SPACES.sub(" ", text)
    text = _RE_NEWLINES.sub("\n", text)
    return text.strip()


def clean_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Bereinigt Bronze-Daten zu Silver.

    Entfernt HTML/BBCode, normalisiert Whitespace, löst forum_id auf,
    konvertiert Timestamps in ISO-Datum, verwirft leere Beiträge und
    dedupliziert auf post_text. Ergebnis: post_id, topic_id, module,
    post_date, post_subject, post_text.
    """
    df = df.copy()

    html_fields = int(
        df["post_text"].str.contains(_HTML_PATTERN, regex=True, na=False).sum()
        + df["post_subject"].str.contains(_HTML_PATTERN, regex=True, na=False).sum()
    )
    bbcode_fields = int(
        df["post_text"].str.contains(_BBCODE_PATTERN, regex=True, na=False).sum()
        + df["post_subject"].str.contains(
            _BBCODE_PATTERN, regex=True, na=False
        ).sum()
    )

    df["post_subject"] = df["post_subject"].fillna("").apply(_clean_markup)
    df["post_text"] = df["post_text"].fillna("").apply(_clean_markup)
    logger.info(
        "Felder mit HTML-Tags: %d, mit BBCode-Tags: %d", html_fields, bbcode_fields
    )
    logger.info("Whitespace normalisiert")

    df["module"] = df["forum_id"].apply(resolve_forum_module)

    def _ts_to_date(ts: int) -> str:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return ""

    df["post_date"] = df["post_time"].apply(_ts_to_date)
    df = df.drop(columns=["forum_id", "post_time"])

    before_empty = len(df)
    df = df[df["post_text"].str.strip() != ""]
    logger.info("Leere Beiträge entfernt: %d", before_empty - len(df))

    before_dup = len(df)
    df = df.drop_duplicates(subset=["post_text"], keep="first")
    logger.info("Duplikate entfernt: %d", before_dup - len(df))

    df = df[["post_id", "topic_id", "module", "post_date", "post_subject", "post_text"]]
    logger.info("Silver bereinigt: %d Beiträge", len(df))
    return df.reset_index(drop=True)


def transform_to_gold(df: pd.DataFrame) -> list[dict]:
    """Überführt Silver-Daten in das Gold-JSONL-Format.

    Kombiniert Titel und Inhalt im full_text-Feld, damit das Embedding
    die zentrale Frage (Titel) gemeinsam mit dem Kontext erfasst.
    """
    records = []
    for _, row in df.iterrows():
        records.append({
            "doc_id": f"forum_{row['post_id']}",
            "source_type": "forum",
            "metadata": {
                "post_id": str(row["post_id"]),
                "topic_id": str(row["topic_id"]),
                "module": str(row["module"]),
                "post_date": str(row["post_date"]),
                "title": str(row["post_subject"]),
            },
            "content": {
                "full_text": f"{row['post_subject']}\n\n{row['post_text']}"
            },
        })
    logger.info("Gold-Records erstellt: %d", len(records))
    return records
