"""Zentrale Konfiguration für den Naive-RAG-Prototypen.

Alle Pfade, Modellnamen und Parameter werden hier definiert.
Kein anderes Modul soll Pfade oder Konstanten hart kodieren.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Projektroot ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Datenpfade ───────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
EVAL_DIR = DATA_DIR / "eval"

# ── Run-Artefakte ────────────────────────────────────────────
RUNS_DIR = PROJECT_ROOT / "runs"
NAIVE_RAG_RUNS_DIR = RUNS_DIR / "naive_rag"
EVAL_RUNS_DIR = RUNS_DIR / "eval"

# ── API-Keys ─────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ── Modelle ──────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE: int = 512
CHUNK_OVERLAP: int = 64

# ── Retrieval ────────────────────────────────────────────────
TOP_K: int = 5

# ── Reproduzierbarkeit ───────────────────────────────────────
RANDOM_SEED: int = 42

# ── Variante ─────────────────────────────────────────────────
VARIANT: str = os.getenv("VARIANT", "v0")


def get_variant_index_dir(variant: str | None = None) -> Path:
    """Pfad zum variantenspezifischen Vektorindex."""
    return INDEX_DIR / (variant or VARIANT)


def get_variant_processed_dir(variant: str | None = None) -> Path:
    """Pfad für variantenspezifische verarbeitete Chunks."""
    return PROCESSED_DIR / (variant or VARIANT)


def get_variant_eval_dir(variant: str | None = None) -> Path:
    """Pfad für variantenspezifische Evaluationsergebnisse."""
    return EVAL_DIR / (variant or VARIANT)
