"""V4 VLM-basierte Bildbeschreibungen.

Extrahiert Bilder aus einer PDF und erzeugt mit gpt-4o eine textuelle
Beschreibung pro Bild. Beschreibungen werden in einem JSONL-Cache
persistiert (analog zu keyword_generator.py).

Idempotent: Bereits getaggte Bilder werden beim Restart übersprungen.
"""

import base64
import json
import logging
import time
from pathlib import Path

import fitz  # PyMuPDF
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from rag.config import (
    V4_IMAGE_DESCRIPTIONS_CACHE,
    V4_VLM_DETAIL,
    V4_VLM_MAX_TOKENS,
    V4_VLM_MIN_PIXEL_THRESHOLD,
    V4_VLM_MODEL,
    V4_VLM_RETRY_BACKOFF_SECONDS,
    V4_VLM_RETRY_MAX_ATTEMPTS,
    V4_VLM_TEMPERATURE,
)

logger = logging.getLogger(__name__)


VLM_PROMPT_SYSTEM = """Du erhältst ein Bild aus einer SelectLine-Schulungsunterlage
(deutsche ERP-Software). Beschreibe das Bild so, dass die Beschreibung für eine
textbasierte Suche nützlich ist.

Wenn es ein UI-Screenshot ist:
- Nenne den Dialog/Bereich/Menü, das gezeigt wird
- Liste sichtbare Felder, Buttons, Reiter mit ihren Beschriftungen auf
- Beschreibe hervorgehobene Elemente (rote Markierungen, eingegebene Werte)

Wenn es ein Diagramm oder eine Tabelle ist:
- Beschreibe Inhalt und Struktur
- Liste Zeilen/Spalten oder Knoten/Kanten konkret auf

Wenn es ein Icon, Logo oder Symbol ist:
- Sage "Icon" oder "Symbol" und beschreibe es kurz

Sei präzise und sachlich. Verwende deutsche Begriffe, wie sie in der Software vorkommen.
Vermeide Marketing-Sprache oder Bewertungen.
Antwortlänge: 1-4 Sätze, je nach Bildkomplexität."""


def _build_image_id(page: int, image_index: int) -> str:
    """Eindeutige ID für ein Bild im V4-Dokument."""
    return f"schulung_auftrag_einsteiger_p{page:03d}_img{image_index:02d}"


def _load_cache(cache_path: Path) -> dict[str, dict]:
    """Lädt bestehenden Cache als Dict image_id → Eintrag."""
    if not cache_path.exists():
        return {}
    cache = {}
    with cache_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                cache[entry["image_id"]] = entry
    return cache


def _append_to_cache(cache_path: Path, entry: dict) -> None:
    """Hängt einen Cache-Eintrag idempotent an die JSONL-Datei."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _image_bytes_to_base64(image_bytes: bytes, fmt: str) -> str:
    """Konvertiert Bild-Bytes zu base64-data-URL."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/{fmt};base64,{b64}"


def _call_vlm(client: OpenAI, image_data_url: str) -> tuple[str, int, int]:
    """Führt VLM-Call durch mit Retry bei Netzwerkfehlern.

    Args:
        client: OpenAI-Client.
        image_data_url: Base64-kodiertes Bild als data-URL.

    Returns:
        (description, input_tokens, output_tokens)
    """
    last_exception: Exception | None = None

    for attempt in range(V4_VLM_RETRY_MAX_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=V4_VLM_MODEL,
                temperature=V4_VLM_TEMPERATURE,
                max_tokens=V4_VLM_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": VLM_PROMPT_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Beschreibe dieses Bild.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data_url,
                                    "detail": V4_VLM_DETAIL,
                                },
                            },
                        ],
                    },
                ],
            )
            description = response.choices[0].message.content.strip()
            return (
                description,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_exception = exc
            if attempt == V4_VLM_RETRY_MAX_ATTEMPTS - 1:
                logger.error(
                    "VLM-Aufruf endgültig fehlgeschlagen nach %d Versuchen: %s",
                    V4_VLM_RETRY_MAX_ATTEMPTS,
                    type(exc).__name__,
                )
                raise
            wait_seconds = V4_VLM_RETRY_BACKOFF_SECONDS[attempt]
            logger.warning(
                "VLM-Aufruf fehlgeschlagen (Versuch %d/%d): %s. Warte %ds.",
                attempt + 1,
                V4_VLM_RETRY_MAX_ATTEMPTS,
                type(exc).__name__,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unerwarteter Zustand in _call_vlm-Retry-Logik")


def describe_images_from_pdf(
    pdf_path: Path,
    cache_path: Path = V4_IMAGE_DESCRIPTIONS_CACHE,
    min_pixel_threshold: int = V4_VLM_MIN_PIXEL_THRESHOLD,
) -> dict[str, dict]:
    """Extrahiert V4-relevante Bilder aus PDF, ruft VLM auf und cached.

    Idempotent: Bereits im Cache vorhandene Bilder werden übersprungen.

    Args:
        pdf_path: Pfad zur Quell-PDF.
        cache_path: Pfad zur JSONL-Cache-Datei.
        min_pixel_threshold: Minimum für maximale Pixeldimension (V4-Filter).

    Returns:
        Dict image_id → vollständiger Cache-Eintrag.
    """
    cache = _load_cache(cache_path)
    logger.info("Cache geladen: %d Einträge", len(cache))

    client = OpenAI()
    doc = fitz.open(pdf_path)

    total_extracted = 0
    total_v4_relevant = 0
    total_new = 0
    total_skipped = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_idx, img in enumerate(image_list):
            total_extracted += 1
            try:
                base_image = doc.extract_image(img[0])
            except Exception as exc:
                logger.warning(
                    "Bild auf Seite %d, idx %d konnte nicht extrahiert"
                    " werden: %s",
                    page_num + 1,
                    img_idx,
                    exc,
                )
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            max_dim = max(width, height)

            if max_dim < min_pixel_threshold:
                continue

            total_v4_relevant += 1
            image_id = _build_image_id(page_num + 1, img_idx + 1)

            if image_id in cache:
                total_skipped += 1
                continue

            image_data_url = _image_bytes_to_base64(
                base_image["image"], base_image["ext"]
            )

            try:
                description, in_tok, out_tok = _call_vlm(client, image_data_url)
            except Exception as exc:
                logger.error(
                    "VLM-Call für %s fehlgeschlagen: %s. Überspringe.",
                    image_id,
                    exc,
                )
                continue

            entry = {
                "image_id": image_id,
                "page": page_num + 1,
                "image_index": img_idx + 1,
                "width": width,
                "height": height,
                "vlm_description": description,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
            }
            _append_to_cache(cache_path, entry)
            cache[image_id] = entry
            total_new += 1

            logger.info(
                "Bild %s beschrieben: %d in, %d out tokens",
                image_id,
                in_tok,
                out_tok,
            )

    doc.close()

    logger.info(
        "Verarbeitet: %d Bilder total, %d V4-relevant, "
        "%d neu beschrieben, %d übersprungen (Cache)",
        total_extracted,
        total_v4_relevant,
        total_new,
        total_skipped,
    )

    return cache
