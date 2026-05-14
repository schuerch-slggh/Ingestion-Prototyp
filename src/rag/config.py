"""Zentrale Konfiguration für den RAG-Prototypen.

Alle Pfade, Modellnamen und Parameter werden hier definiert.
Kein anderes Modul soll Pfade oder Konstanten hart kodieren.
"""

import math
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Projektroot ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Datenaufbereitung (variantenunabhängig) ──────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "bronze"        # Rohdaten
INTERIM_DIR = DATA_DIR / "silver"    # Bereinigt
GOLD_DIR = DATA_DIR / "gold"         # Einheitliches Zwischenformat (JSONL)

# ── Evaluation (variantenunabhängig) ─────────────────────────
TESTSET_PATH: Path = DATA_DIR / "eval" / "testset_v1.jsonl"

# RAGAS-Judge-Konfiguration (siehe Kap. 7 der Arbeit)
RAGAS_JUDGE_MODEL: str = "gpt-4o"
RAGAS_JUDGE_TEMPERATURE: float = 0.0
RAGAS_JUDGE_SEED: int = 42

# ── Ingestion-Artefakte (variantenabhängig) ──────────────────
CHUNKS_DIR = DATA_DIR / "chunks"     # Pro Variante eigene Chunks
INDEX_DIR = DATA_DIR / "index"       # Pro Variante eigener Vektorindex
EVAL_DIR = DATA_DIR / "eval"         # Pro Variante eigene Evaluation

# ── Run-Artefakte ────────────────────────────────────────────
RUNS_DIR = PROJECT_ROOT / "runs"
EVAL_RUNS_DIR = RUNS_DIR / "eval"

# ── API-Keys ─────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ── Modelle ──────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# ── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE: int = 1000
CHUNK_OVERLAP: int = 150

# ── Retrieval ────────────────────────────────────────────────
TOP_K: int = 5

# ── Reproduzierbarkeit ───────────────────────────────────────
RANDOM_SEED: int = 42

# ── V2 Schlüsselwort-Caches und BM25-Index ──────────────────────────────────
V2_KEYWORDS_CACHE_PATH: Path = DATA_DIR / "cache" / "v2_keywords.jsonl"
V2_BM25_INDEX_PATH: Path = DATA_DIR / "index" / "v2" / "bm25.pkl"

# ── V3 Recency-Re-Ranking (Grofsky 2025) ────────────────────────────────────
V3_ALPHA: float = 0.8
V3_HALF_LIFE_DAYS: float = 1825.0  # 5 Jahre; R(1825) = 0.5
V3_DECAY_RATE: float = math.log(2) / V3_HALF_LIFE_DAYS
V3_PRE_RERANK_TOP_K: int = 10
V3_RECENCY_DATE_FIELDS: dict[str, str] = {
    "forum": "post_date",
    "ticket": "processed_date",
}

# ── V4 VLM Image Description ─────────────────────────────────────────────────
V4_VLM_MODEL: str = "gpt-4o"
V4_VLM_DETAIL: str = "high"
V4_VLM_TEMPERATURE: float = 0.2
V4_VLM_MAX_TOKENS: int = 300
V4_VLM_RETRY_MAX_ATTEMPTS: int = 5
V4_VLM_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (2, 5, 15, 30, 60)
V4_VLM_MIN_PIXEL_THRESHOLD: int = 300
V4_VLM_SOURCE_PDF: Path = (
    RAW_DIR / "schulungsunterlagen"
    / "Schulungsunterlagen Auftrag Einsteiger.pdf"
)
V4_IMAGE_DESCRIPTIONS_CACHE: Path = DATA_DIR / "cache" / "v4_image_descriptions.jsonl"
V4_SCHULUNG_PDF_NAME: str = "Schulungsunterlagen Auftrag Einsteiger.pdf"
V4_IMAGE_MARKER_TEMPLATE: str = "[Bild: {description}]"
V4_KEYWORDS_CACHE: Path = DATA_DIR / "cache" / "v4_keywords.jsonl"
V4_BM25_INDEX_PATH: Path = DATA_DIR / "index" / "v4" / "bm25.pkl"

# ── Variante ─────────────────────────────────────────────────
VARIANT: str = os.getenv("VARIANT", "v0")


def get_variant_index_dir(variant: str | None = None) -> Path:
    """Pfad zum variantenspezifischen Vektorindex."""
    return INDEX_DIR / (variant or VARIANT)


def get_variant_chunks_dir(variant: str | None = None) -> Path:
    """Pfad für variantenspezifische Chunks."""
    return CHUNKS_DIR / (variant or VARIANT)


def get_variant_eval_dir(variant: str | None = None) -> Path:
    """Pfad für variantenspezifische Evaluationsergebnisse."""
    return EVAL_DIR / (variant or VARIANT)
