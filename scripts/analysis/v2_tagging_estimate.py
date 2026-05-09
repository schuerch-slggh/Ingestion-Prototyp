"""Pre-Flight: Schätzt LLM-Tagging-Kosten für V2-Lauf ohne API-Calls.

Lädt Gold-JSONL, ruft V1-Chunker und strukturelle Metadaten-Anreicherung
auf (kein LLM-Tagger!), summiert Tokens für Tagging-Prompts.
Soll vor dem Tagging-Lauf gerunnt werden.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import tiktoken

from rag.config import GOLD_DIR
from rag.index.chunking_v2 import _enrich_with_metadata
from rag.index.llm_tagger import (
    GPT_4O_MINI_INPUT_COST_PER_MTOK,
    GPT_4O_MINI_OUTPUT_COST_PER_MTOK,
    TOKEN_TRUNCATION_LIMIT,
    _SYSTEM_PROMPT,
)
from rag.index.chunking_v1 import chunk_documents_v1

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GOLD_FILES = [
    "forum.jsonl",
    "tickets.jsonl",
    "handbuecher.jsonl",
    "modulbeschreibungen.jsonl",
    "schulungsunterlagen.jsonl",
]

COST_WARN_THRESHOLD = 5.00
_ENC = tiktoken.get_encoding("cl100k_base")
_SYSTEM_TOKENS = len(_ENC.encode(_SYSTEM_PROMPT))
_OUTPUT_TOKENS_PER_CHUNK = 50  # conservative estimate for tag JSON


def main() -> None:
    grand_total_chunks = 0
    grand_total_input_tokens = 0
    grand_total_output_tokens = 0

    for filename in GOLD_FILES:
        path = GOLD_DIR / filename
        if not path.exists():
            logger.warning("Gold-Datei fehlt: %s", path)
            continue

        entries = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        chunks = chunk_documents_v1(entries)
        chunks = _enrich_with_metadata(chunks, entries)

        input_tokens = 0
        for chunk in chunks:
            text_toks = len(_ENC.encode(chunk["text"]))
            input_tokens += _SYSTEM_TOKENS + min(
                text_toks, TOKEN_TRUNCATION_LIMIT
            )

        output_tokens = len(chunks) * _OUTPUT_TOKENS_PER_CHUNK
        grand_total_chunks += len(chunks)
        grand_total_input_tokens += input_tokens
        grand_total_output_tokens += output_tokens

        logger.info(
            "  %-35s %6d Chunks, ~%dK Input-Tokens",
            filename,
            len(chunks),
            input_tokens // 1000,
        )

    estimated_cost = (
        grand_total_input_tokens / 1_000_000 * GPT_4O_MINI_INPUT_COST_PER_MTOK
        + grand_total_output_tokens
        / 1_000_000
        * GPT_4O_MINI_OUTPUT_COST_PER_MTOK
    )

    logger.info("=== V2 LLM-Tagging Pre-Flight-Schätzung ===")
    logger.info("Total Chunks:              %d", grand_total_chunks)
    logger.info(
        "Geschätzte Input-Tokens:   %d (~%dM)",
        grand_total_input_tokens,
        grand_total_input_tokens // 1_000_000,
    )
    logger.info(
        "Geschätzte Output-Tokens:  %d (~%dK, %d pro Chunk)",
        grand_total_output_tokens,
        grand_total_output_tokens // 1000,
        _OUTPUT_TOKENS_PER_CHUNK,
    )
    logger.info("Geschätzte Kosten:         %.4f USD", estimated_cost)

    if estimated_cost > COST_WARN_THRESHOLD:
        logger.warning(
            "WARNUNG: Geschätzte Kosten %.4f USD > %.2f USD Schwellwert. "
            "Vor Lauf manuell prüfen.",
            estimated_cost,
            COST_WARN_THRESHOLD,
        )
        sys.exit(1)

    logger.info(
        "Kosten OK (%.4f USD <= %.2f USD) – bereit für Tagging-Lauf.",
        estimated_cost,
        COST_WARN_THRESHOLD,
    )


if __name__ == "__main__":
    main()
