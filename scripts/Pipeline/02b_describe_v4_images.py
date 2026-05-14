"""V4 VLM-Bildbeschreibungen erzeugen.

Lädt das Schulungsunterlagen-PDF, extrahiert V4-relevante Bilder (>=300 px)
und erzeugt mit gpt-4o eine textuelle Beschreibung pro Bild.
Beschreibungen werden in data/cache/v4_image_descriptions.jsonl persistiert.

Idempotent: Bei einem Restart werden bereits getaggte Bilder übersprungen.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import V4_IMAGE_DESCRIPTIONS_CACHE, V4_VLM_SOURCE_PDF
from rag.index.vlm_image_describer import describe_images_from_pdf

# gpt-4o Pricing (Stand Mai 2026, https://openai.com/api/pricing/)
GPT_4O_INPUT_COST_PER_MTOK: float = 2.50
GPT_4O_OUTPUT_COST_PER_MTOK: float = 10.00


def main() -> None:
    if not V4_VLM_SOURCE_PDF.exists():
        print(f"FEHLER: {V4_VLM_SOURCE_PDF} nicht gefunden")
        sys.exit(1)

    print(f"V4-Bildbeschreibungen für: {V4_VLM_SOURCE_PDF.name}")
    print(f"Cache: {V4_IMAGE_DESCRIPTIONS_CACHE}")
    print()

    cache = describe_images_from_pdf(V4_VLM_SOURCE_PDF)

    total_in = sum(e["input_tokens"] for e in cache.values())
    total_out = sum(e["output_tokens"] for e in cache.values())
    cost = (
        total_in / 1_000_000 * GPT_4O_INPUT_COST_PER_MTOK
        + total_out / 1_000_000 * GPT_4O_OUTPUT_COST_PER_MTOK
    )

    print(f"\nFertig: {len(cache)} Bilder beschrieben")
    print(f"  Input-Tokens total:  {total_in:,}")
    print(f"  Output-Tokens total: {total_out:,}")
    print(f"  Kosten: ${cost:.2f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    main()
