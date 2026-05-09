"""LLM-Tagging für V2-Chunks via gpt-4o-mini.

Reichert Chunks mit LLM-generierten Tags an. Drei Kategorien:
- module_tags (max 2): SelectLine-Module
- thema_tags (max 3): Funktionale Bereiche
- typ_tags (max 1): Dokumenttypen

Tags werden als kommagetrennte Strings in Chunk-Metadaten gespeichert
(ChromaDB-Kompatibilität). Caching nach chunk_id (JSONL-Datei) für
Crash-Resistenz und reproduzierbare Läufe.
"""

import json
import logging
from pathlib import Path

import tiktoken
from openai import OpenAI
from tqdm import tqdm

from rag.config import V2_TAGS_CACHE_PATH
from rag.index.tag_taxonomy import MAX_TAGS, MODULE_TAGS, THEMA_TAGS, TYP_TAGS

logger = logging.getLogger(__name__)

# ── Kosten-Konstanten (Stand Mai 2026, https://openai.com/api/pricing/) ──────
GPT_4O_MINI_INPUT_COST_PER_MTOK: float = 0.15
GPT_4O_MINI_OUTPUT_COST_PER_MTOK: float = 0.60

# ── Tagging-Parameter ────────────────────────────────────────────────────────
TAGGING_MODEL: str = "gpt-4o-mini"
TAGGING_TEMPERATURE: float = 0.0
TAGGING_SEED: int = 42
TOKEN_TRUNCATION_LIMIT: int = 2000
UNTAGGED_RATE_ABORT_THRESHOLD: float = 0.05

_ENC = tiktoken.get_encoding("cl100k_base")

_WHITELISTS: dict[str, frozenset[str]] = {
    "module_tags": MODULE_TAGS,
    "thema_tags": THEMA_TAGS,
    "typ_tags": TYP_TAGS,
}

_SYSTEM_PROMPT = (
    "Du bist ein Klassifikator für SelectLine-ERP-Dokumentations-Chunks.\n"
    "Weise dem folgenden Chunk Tags aus drei geschlossenen Listen zu:\n\n"
    "1. module_tags (max 2): SelectLine-Module, die im Chunk thematisiert werden.\n"
    "2. thema_tags (max 3): Funktionale Bereiche. 'Sonstiges' nur als Fallback.\n"
    "3. typ_tags (max 1): Charakter des Chunk-Inhalts.\n\n"
    "Wähle ausschliesslich aus den vorgegebenen Listen. Bei Unklarheit\n"
    "oder fehlendem Bezug: leere Liste."
)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _build_response_schema() -> dict:
    """Erzeugt JSON-Schema für OpenAI Structured Outputs.

    Tag-Listen als enum-Einschränkung, sortiert für Determinismus.
    """
    return {
        "name": "chunk_tags",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "module_tags": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(MODULE_TAGS)},
                },
                "thema_tags": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(THEMA_TAGS)},
                },
                "typ_tags": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(TYP_TAGS)},
                },
            },
            "required": ["module_tags", "thema_tags", "typ_tags"],
            "additionalProperties": False,
        },
    }


def _build_tagging_prompt(chunk_text: str) -> list[dict]:
    """Baut den User-Message-Prompt für einen Chunk.

    Kürzt Text auf TOKEN_TRUNCATION_LIMIT Tokens (tiktoken cl100k_base).
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
) -> tuple[dict, int, int]:
    """Führt OpenAI-Call mit Structured Output durch.

    Args:
        messages: Chat-Messages (system + user).
        schema: JSON-Schema-Dict für response_format.

    Returns:
        (geparstes Tags-Dict, input_tokens, output_tokens).
    """
    client = OpenAI()
    response = client.chat.completions.create(
        model=TAGGING_MODEL,
        temperature=TAGGING_TEMPERATURE,
        seed=TAGGING_SEED,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": schema},
    )
    tags = json.loads(response.choices[0].message.content)
    return tags, response.usage.prompt_tokens, response.usage.completion_tokens


def _validate_tags(raw_tags: dict) -> dict:
    """Filtert ungültige Tags und wendet MAX_TAGS-Limits an.

    Returns:
        Validiertes Dict mit Listen der gültigen Tags.
    """
    result: dict[str, list[str]] = {}
    for field, whitelist in _WHITELISTS.items():
        raw = raw_tags.get(field, [])
        if not isinstance(raw, list):
            raw = []
        valid = [t for t in raw if t in whitelist]
        result[field] = valid[: MAX_TAGS[field]]
    return result


def _serialize_tags(tags: list[str]) -> str:
    """Serialisiert Tag-Liste für ChromaDB als kommagetrennten String."""
    return ",".join(tags)


def _load_cache(cache_path: Path) -> dict[str, dict]:
    """Lädt JSONL-Cache als Dict {chunk_id: tags}.

    Robust gegen leere oder nicht existente Datei.
    """
    if not cache_path.exists():
        return {}
    result: dict[str, dict] = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            chunk_id = entry.pop("chunk_id")
            result[chunk_id] = entry
        except (json.JSONDecodeError, KeyError):
            logger.warning("Ungültige Cache-Zeile übersprungen: %r", line[:80])
    return result


def _append_cache_entry(
    cache_path: Path, chunk_id: str, tags: dict
) -> None:
    """Appendet einen Cache-Eintrag sofort (für Crash-Resistenz).

    Args:
        cache_path: Pfad zur Cache-Datei.
        chunk_id: ID des Chunks.
        tags: Validiertes Tags-Dict mit Listen.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"chunk_id": chunk_id, **tags}
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


def tag_chunks(
    chunks: list[dict],
    cache_path: Path | None = None,
) -> list[dict]:
    """Reichert Chunks mit LLM-generierten Tags an.

    Lädt vorhandenen Cache, taggt nur ungetaggte Chunks via gpt-4o-mini,
    persistiert Tags in Cache und im Chunk-Metadaten-Dict.

    Args:
        chunks: Liste der Chunks aus _enrich_with_metadata(). Werden
                modifiziert in-place (Felder module_tags, thema_tags,
                typ_tags ergänzt).
        cache_path: Pfad zur Cache-Datei. Falls None, V2_TAGS_CACHE_PATH.

    Returns:
        Liste der Chunks (gleiche Reihenfolge, modifiziert in-place).

    Raises:
        RuntimeError: Wenn >5% der Chunks komplett ungetaggt sind.
    """
    if cache_path is None:
        cache_path = V2_TAGS_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache = _load_cache(cache_path)
    schema = _build_response_schema()
    uncached = [c for c in chunks if c["id"] not in cache]

    total_input_tokens = 0
    total_output_tokens = 0

    for chunk in tqdm(uncached, desc="LLM-Tagging", unit="chunk"):
        messages = _build_tagging_prompt(chunk["text"])
        raw_tags, in_tok, out_tok = _call_llm(messages, schema)
        validated = _validate_tags(raw_tags)

        cache[chunk["id"]] = validated
        _append_cache_entry(cache_path, chunk["id"], validated)

        total_input_tokens += in_tok
        total_output_tokens += out_tok

    # Tags auf alle Chunks anwenden (Cache + neu getaggt)
    empty_tags: dict[str, list[str]] = {
        "module_tags": [],
        "thema_tags": [],
        "typ_tags": [],
    }
    for chunk in chunks:
        tags = cache.get(chunk["id"], empty_tags)
        chunk["metadata"]["module_tags"] = _serialize_tags(
            tags.get("module_tags", [])
        )
        chunk["metadata"]["thema_tags"] = _serialize_tags(
            tags.get("thema_tags", [])
        )
        chunk["metadata"]["typ_tags"] = _serialize_tags(
            tags.get("typ_tags", [])
        )

    # Ungetaggt-Rate prüfen
    untagged = sum(
        1
        for c in chunks
        if not c["metadata"]["module_tags"]
        and not c["metadata"]["thema_tags"]
        and not c["metadata"]["typ_tags"]
    )
    untagged_rate = untagged / len(chunks) if chunks else 0.0

    cost = (
        total_input_tokens / 1_000_000 * GPT_4O_MINI_INPUT_COST_PER_MTOK
        + total_output_tokens / 1_000_000 * GPT_4O_MINI_OUTPUT_COST_PER_MTOK
    )

    logger.info(
        "LLM-Tagging: %d aus Cache, %d neu getaggt, "
        "Kosten: %.4f USD, Ungetaggt-Rate: %.1f%%",
        len(chunks) - len(uncached),
        len(uncached),
        cost,
        untagged_rate * 100,
    )

    if untagged_rate > UNTAGGED_RATE_ABORT_THRESHOLD:
        raise RuntimeError(
            f"Ungetaggt-Rate {untagged_rate:.1%} > "
            f"{UNTAGGED_RATE_ABORT_THRESHOLD:.1%} – Tagging-Lauf abgebrochen."
        )

    return chunks
