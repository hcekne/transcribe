from __future__ import annotations

from pathlib import Path

from transcribe_cli.chunker import Chunk
from transcribe_cli.output import build_raw_payload
from transcribe_cli.transcriber import ChunkTranscript


def test_merge_segments_offsets_chunk_times(tmp_path: Path) -> None:
    chunk_path = tmp_path / "chunk.m4a"
    chunk_path.write_bytes(b"fake")
    transcript = ChunkTranscript(
        chunk=Chunk(index=2, path=chunk_path, start_seconds=60.0, end_seconds=120.0),
        response={
            "text": "hello",
            "segments": [{"speaker": "A", "start": 1.5, "end": 3.0, "text": "hello"}],
        },
    )

    payload = build_raw_payload(
        source_path=Path("input.wav"),
        normalized_path=Path("normalized.m4a"),
        model="gpt-4o-transcribe-diarize",
        language=None,
        diarize=True,
        target_chunk_bytes=24_000_000,
        transcripts=[transcript],
    )

    assert payload["segments"][0]["start"] == 61.5
    assert payload["segments"][0]["end"] == 63.0
