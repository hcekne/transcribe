from __future__ import annotations

import pytest

from transcribe_cli.config import DEFAULT_MODEL, DIARIZE_MODEL, resolve_model


def test_resolve_model_defaults_to_standard_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)

    model, diarize, warning = resolve_model(None, False)

    assert model == DEFAULT_MODEL
    assert diarize is False
    assert warning is None


def test_diarize_switches_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)

    model, diarize, warning = resolve_model(None, True)

    assert model == DIARIZE_MODEL
    assert diarize is True
    assert warning is None


def test_diarize_rejects_explicit_non_diarize_model() -> None:
    with pytest.raises(ValueError):
        resolve_model("gpt-4o-transcribe", True)
