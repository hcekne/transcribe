from __future__ import annotations

from transcribe_cli.chunker import SilenceRange, plan_chunk_boundaries


def test_plan_chunk_boundaries_prefers_silence_before_limit() -> None:
    boundaries = plan_chunk_boundaries(
        duration_seconds=300,
        source_size_bytes=54_000_000,
        target_bytes=24_000_000,
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
        silences=[],
    ) == [(0.0, 120)]
