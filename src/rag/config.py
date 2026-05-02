"""Zentrale Konfiguration für den RAG-Prototypen.

Alle Pfade, Modellnamen und Parameter werden hier definiert.
Kein anderes Modul soll Pfade oder Konstanten hart kodieren.
"""

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
