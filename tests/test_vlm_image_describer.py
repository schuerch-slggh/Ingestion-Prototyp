"""Tests für vlm_image_describer (AP-10). Alle VLM-Calls gemockt."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.vlm_image_describer import (
    V4_VLM_RETRY_MAX_ATTEMPTS,
    _build_image_id,
    _call_vlm,
    _image_bytes_to_base64,
    _load_cache,
)

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _make_mock_client(side_effects: list):
    """Erstellt Mock-Client der side_effects der Reihe nach abarbeitet."""

    class _Completions:
        _calls = 0

        @staticmethod
        def create(*args, **kwargs):
            idx = _Completions._calls
            _Completions._calls += 1
            effect = side_effects[min(idx, len(side_effects) - 1)]
            if isinstance(effect, Exception):
                raise effect
            return effect

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    return _Client()


def _make_success_response(text: str = "Test-Beschreibung"):
    class _Usage:
        prompt_tokens = 1000
        completion_tokens = 50

    class _Message:
        content = text

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]
        usage = _Usage()

    return _Response()


# ── Tests ────────────────────────────────────────────────────────────────────


def test_build_image_id_format() -> None:
    """ID-Format ist korrekt und zero-padded."""
    assert _build_image_id(42, 1) == "schulung_auftrag_einsteiger_p042_img01"
    assert _build_image_id(1, 10) == "schulung_auftrag_einsteiger_p001_img10"


def test_load_cache_empty_when_file_missing(tmp_path: Path) -> None:
    """Cache ist leer wenn Datei nicht existiert."""
    cache = _load_cache(tmp_path / "nonexistent.jsonl")
    assert cache == {}


def test_load_cache_reads_existing_entries(tmp_path: Path) -> None:
    """Cache lädt bestehende JSONL-Einträge korrekt."""
    cache_file = tmp_path / "test.jsonl"
    cache_file.write_text(
        json.dumps({"image_id": "abc", "vlm_description": "Test"}) + "\n",
        encoding="utf-8",
    )
    cache = _load_cache(cache_file)
    assert "abc" in cache
    assert cache["abc"]["vlm_description"] == "Test"


def test_call_vlm_retries_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """VLM-Call wird bei APIConnectionError einmal wiederholt."""
    import httpx
    from openai import APIConnectionError

    monkeypatch.setattr("rag.index.vlm_image_describer.time.sleep", lambda s: None)

    error = APIConnectionError(request=httpx.Request("POST", "http://test"))
    client = _make_mock_client([error, _make_success_response()])

    description, in_tok, out_tok = _call_vlm(client, "data:image/png;base64,xyz")

    assert description == "Test-Beschreibung"
    assert in_tok == 1000
    assert out_tok == 50


def test_call_vlm_raises_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nach V4_VLM_RETRY_MAX_ATTEMPTS Versuchen wird Exception propagiert."""
    import httpx
    from openai import APIConnectionError

    monkeypatch.setattr("rag.index.vlm_image_describer.time.sleep", lambda s: None)

    error = APIConnectionError(request=httpx.Request("POST", "http://test"))
    call_log: list[int] = []

    class _Completions:
        @staticmethod
        def create(*args, **kwargs):
            call_log.append(1)
            raise error

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    with pytest.raises(APIConnectionError):
        _call_vlm(_Client(), "data:image/png;base64,xyz")

    assert len(call_log) == V4_VLM_RETRY_MAX_ATTEMPTS


def test_image_bytes_to_base64() -> None:
    """Base64-data-URL hat korrektes Präfix."""
    result = _image_bytes_to_base64(b"\x89PNG\r\n", "png")
    assert result.startswith("data:image/png;base64,")
