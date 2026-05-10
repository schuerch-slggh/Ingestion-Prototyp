"""Schlüsselwort-Generierung für V2-Chunks via gpt-4o-mini.

Reichert Chunks mit 5–12 LLM-generierten Schlüsselwörtern an.
Synonyme dürfen eingebracht werden. Keywords werden als
kommagetrennter String in chunk["metadata"]["keywords"] gespeichert.
Caching nach chunk_id (JSONL) für Crash-Resistenz.
"""

import json
import logging
from pathlib import Path

import tiktoken
from openai import OpenAI
from tqdm import tqdm

from rag.config import V2_KEYWORDS_CACHE_PATH

logger = logging.getLogger(__name__)

# ── Kosten-Konstanten (Stand Mai 2026, https://openai.com/api/pricing/) ──────
GPT_4O_MINI_INPUT_COST_PER_MTOK: float = 0.15
GPT_4O_MINI_OUTPUT_COST_PER_MTOK: float = 0.60

# ── Generator-Parameter ──────────────────────────────────────────────────────
KEYWORDS_MODEL: str = "gpt-4o-mini"
KEYWORDS_TEMPERATURE: float = 0.0
KEYWORDS_SEED: int = 42
KEYWORDS_MIN_PER_CHUNK: int = 5
KEYWORDS_MAX_PER_CHUNK: int = 12
KEYWORDS_TARGET_PER_CHUNK: int = 8
KEYWORD_MIN_CHARS: int = 2
KEYWORD_MAX_CHARS: int = 60
TOKEN_TRUNCATION_LIMIT: int = 2000
LOW_KEYWORDS_RATE_ABORT_THRESHOLD: float = 0.05

_ENC = tiktoken.get_encoding("cl100k_base")

_SYSTEM_PROMPT = (
    "Du bist ein Schlüsselwort-Extraktor für SelectLine-ERP-Dokumentations-Chunks.\n"
    "Deine Aufgabe: Extrahiere 5 bis 12 Schlüsselwörter, die den Inhalt des\n"
    "Chunks präzise beschreiben.\n\n"
    "Regeln:\n"
    "- Schlüsselwörter sollen den thematischen Kern des Chunks erfassen.\n"
    "- Du darfst gängige Synonyme einbringen, die im Text nicht wörtlich\n"
    "  vorkommen, aber dasselbe bezeichnen (z. B. 'Lieferant' für 'Kreditor',\n"
    "  'MWST' für 'Mehrwertsteuer').\n"
    "- Schlüsselwörter sollen kurz und prägnant sein (1-3 Wörter pro Schlüsselwort).\n"
    "- Vermeide allgemeine Wörter wie 'und', 'oder', 'Beispiel'.\n"
    "- Konzentriere dich auf Fachbegriffe, Aktionen und Datenobjekte.\n\n"
    "Gib das Ergebnis als JSON zurück mit dem Feld 'keywords' als Array von Strings."
)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _build_response_schema() -> dict:
    """Erzeugt JSON-Schema für OpenAI Structured Outputs."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "chunk_keywords",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
        },
    }


def _build_keyword_prompt(chunk_text: str) -> list[dict]:
    """Baut den User-Message-Prompt für einen Chunk.

    Kürzt Text auf TOKEN_TRUNCATION_LIMIT Tokens.
    """
    tokens = _ENC.encode(chunk_text)
    if len(tokens) > TOKEN_TRUNCATION_LIMIT:
        chunk_text = _ENC.decode(tokens[:TOKEN_TRUNCATION_LIMIT])
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": chunk_text},
    ]


def _call_llm(
    messages: list[dict], schema: dict
) -> tuple[list[str], int, int]:
    """Führt OpenAI-Call durch und gibt Keywords und Token-Counts zurück.

    Returns:
        (keywords_list, input_tokens, output_tokens).
    """
    client = OpenAI()
    response = client.chat.completions.create(
        model=KEYWORDS_MODEL,
        temperature=KEYWORDS_TEMPERATURE,
        seed=KEYWORDS_SEED,
        messages=messages,
        response_format=schema,
    )
    raw = json.loads(response.choices[0].message.content)
    keywords = raw.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = []
    return keywords, response.usage.prompt_tokens, response.usage.completion_tokens


def _validate_keywords(raw_keywords: list[str]) -> list[str]:
    """Filtert Keywords, die zu kurz oder zu lang sind.

    Returns:
        Liste gültiger Keywords (KEYWORD_MIN_CHARS–KEYWORD_MAX_CHARS).
    """
    return [
        kw
        for kw in raw_keywords
        if isinstance(kw, str)
        and KEYWORD_MIN_CHARS <= len(kw.strip()) <= KEYWORD_MAX_CHARS
    ]


def _serialize_keywords(keywords: list[str]) -> str:
    """Serialisiert Keyword-Liste als kommagetrennten String für ChromaDB."""
    return ",".join(kw.strip() for kw in keywords)


def _load_cache(cache_path: Path) -> dict[str, list[str]]:
    """Lädt JSONL-Cache als Dict {chunk_id: keywords}.

    Robust gegen leere oder nicht existente Datei.
    """
    if not cache_path.exists():
        return {}
    result: dict[str, list[str]] = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            chunk_id = entry["chunk_id"]
            result[chunk_id] = entry.get("keywords", [])
        except (json.JSONDecodeError, KeyError):
            logger.warning("Ungültige Cache-Zeile übersprungen: %r", line[:80])
    return result


def _append_cache_entry(
    cache_path: Path, chunk_id: str, keywords: list[str]
) -> None:
    """Appendet einen Cache-Eintrag sofort (Crash-Resistenz)."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"chunk_id": chunk_id, "keywords": keywords}
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


def enrich_with_keywords(
    chunks: list[dict],
    cache_path: Path | None = None,
) -> list[dict]:
    """Reichert Chunks mit LLM-generierten Schlüsselwörtern an.

    Lädt vorhandenen Cache, generiert Keywords nur für ungetaggte Chunks
    via gpt-4o-mini, persistiert sie in Cache und im Chunk-Metadaten-Dict
    (Feld 'keywords' als kommagetrennter String).

    Args:
        chunks: Chunks aus _enrich_with_metadata(). In-place modifiziert.
        cache_path: Pfad zur Cache-Datei. Falls None, V2_KEYWORDS_CACHE_PATH.

    Returns:
        Chunks (gleiche Reihenfolge, in-place modifiziert).

    Raises:
        RuntimeError: Wenn >5% der Chunks weniger als 3 valide Keywords haben.
    """
    if cache_path is None:
        cache_path = V2_KEYWORDS_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache = _load_cache(cache_path)
    schema = _build_response_schema()
    uncached = [c for c in chunks if c["id"] not in cache]

    total_input_tokens = 0
    total_output_tokens = 0

    for chunk in tqdm(uncached, desc="Keyword-Generierung", unit="chunk"):
        messages = _build_keyword_prompt(chunk["text"])
        raw_kws, in_tok, out_tok = _call_llm(messages, schema)
        validated = _validate_keywords(raw_kws)

        cache[chunk["id"]] = validated
        _append_cache_entry(cache_path, chunk["id"], validated)

        total_input_tokens += in_tok
        total_output_tokens += out_tok

    # Keywords auf alle Chunks anwenden (Cache + neu generiert)
    for chunk in chunks:
        keywords = cache.get(chunk["id"], [])
        chunk["metadata"]["keywords"] = _serialize_keywords(keywords)

    # Qualitäts-Check: Chunks mit < 3 Keywords
    low_kw_count = sum(
        1
        for c in chunks
        if len([k for k in c["metadata"]["keywords"].split(",") if k]) < 3
    )
    low_kw_rate = low_kw_count / len(chunks) if chunks else 0.0

    cost = (
        total_input_tokens / 1_000_000 * GPT_4O_MINI_INPUT_COST_PER_MTOK
        + total_output_tokens / 1_000_000 * GPT_4O_MINI_OUTPUT_COST_PER_MTOK
    )

    logger.info(
        "Keyword-Generierung: %d aus Cache, %d neu, "
        "Kosten: %.4f USD, <3-Keyword-Rate: %.1f%%",
        len(chunks) - len(uncached),
        len(uncached),
        cost,
        low_kw_rate * 100,
    )

    if low_kw_rate > LOW_KEYWORDS_RATE_ABORT_THRESHOLD:
        raise RuntimeError(
            f"<3-Keyword-Rate {low_kw_rate:.1%} > "
            f"{LOW_KEYWORDS_RATE_ABORT_THRESHOLD:.1%} – Lauf abgebrochen."
        )

    return chunks
