from __future__ import annotations

from pathlib import Path

import pytest

from transcribe_cli.audio import AudioMetadata
from transcribe_cli.chunker import SilenceRange, create_chunks, plan_chunk_boundaries


def test_plan_chunk_boundaries_prefers_silence_before_limit() -> None:
    boundaries = plan_chunk_boundaries(
        duration_seconds=300,
        source_size_bytes=54_000_000,
        target_bytes=24_000_000,
        target_seconds=1350,
        silences=[SilenceRange(118, 122), SilenceRange(238, 242)],
    )

    assert boundaries[0] == (0.0, 120.0)
    assert boundaries[1][0] == 120.0
    assert boundaries[-1][1] == 300


def test_plan_chunk_boundaries_returns_single_chunk_when_under_limit() -> None:
    assert plan_chunk_boundaries(
        duration_seconds=120,
        source_size_bytes=1_000_000,
        target_bytes=24_000_000,
        target_seconds=1350,
        silences=[],
    ) == [(0.0, 120)]


def test_plan_chunk_boundaries_enforces_duration_even_when_file_is_under_size_limit() -> None:
    boundaries = plan_chunk_boundaries(
        duration_seconds=3000,
        source_size_bytes=1_000_000,
        target_bytes=24_000_000,
        target_seconds=1350,
        silences=[SilenceRange(1338, 1342), SilenceRange(2678, 2682)],
    )

    assert boundaries == [(0.0, 1340.0), (1340.0, 2680.0), (2680.0, 3000)]


def test_create_chunks_splits_long_audio_under_byte_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.m4a"
    source.write_bytes(b"source")

    monkeypatch.setattr(
        "transcribe_cli.chunker.probe_audio",
        lambda path: AudioMetadata(duration_seconds=3000, size_bytes=1_000_000),
    )
    monkeypatch.setattr(
        "transcribe_cli.chunker.detect_silences",
        lambda path: [SilenceRange(1338, 1342), SilenceRange(2678, 2682)],
    )

    def extract_stub(source: Path, destination: Path, start: float, end: float) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"chunk")
        return destination

    monkeypatch.setattr("transcribe_cli.chunker.extract_audio_segment", extract_stub)

    chunks = create_chunks(
        source,
        tmp_path / "chunks",
        target_bytes=24_000_000,
        target_seconds=1350,
    )

    assert [(chunk.start_seconds, chunk.end_seconds) for chunk in chunks] == [
        (0.0, 1340.0),
        (1340.0, 2680.0),
        (2680.0, 3000),
    ]
