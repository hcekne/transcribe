from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcribe_cli.time_utils import format_timestamp
from transcribe_cli.transcriber import ChunkTranscript


def write_outputs(
    output_dir: Path,
    source_path: Path,
    normalized_path: Path,
    model: str,
    language: str | None,
    diarize: bool,
    target_chunk_bytes: int,
    transcripts: list[ChunkTranscript],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_payload = build_raw_payload(
        source_path=source_path,
        normalized_path=normalized_path,
        model=model,
        language=language,
        diarize=diarize,
        target_chunk_bytes=target_chunk_bytes,
        transcripts=transcripts,
    )
    clean_markdown = build_clean_markdown(raw_payload)

    clean_path = output_dir / "transcript_clean.md"
    raw_path = output_dir / "transcript_raw.json"

    clean_path.write_text(clean_markdown, encoding="utf-8")
    raw_path.write_text(json.dumps(raw_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return clean_path, raw_path


def build_raw_payload(
    source_path: Path,
    normalized_path: Path,
    model: str,
    language: str | None,
    diarize: bool,
    target_chunk_bytes: int,
    transcripts: list[ChunkTranscript],
) -> dict[str, Any]:
    chunks = []
    for transcript in transcripts:
        chunk = transcript.chunk
        chunks.append(
            {
                "index": chunk.index,
                "path": str(chunk.path),
                "start_seconds": chunk.start_seconds,
                "end_seconds": chunk.end_seconds,
                "size_bytes": chunk.size_bytes,
                "response": transcript.response,
            }
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "normalized_audio": str(normalized_path),
        "model": model,
        "language": language,
        "diarize": diarize,
        "target_chunk_bytes": target_chunk_bytes,
        "text": merge_text(transcripts),
        "segments": merge_segments(transcripts) if diarize else [],
        "chunks": chunks,
    }


def merge_text(transcripts: list[ChunkTranscript]) -> str:
    parts = []
    for transcript in transcripts:
        text = str(transcript.response.get("text") or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def merge_segments(transcripts: list[ChunkTranscript]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for transcript in transcripts:
        offset = transcript.chunk.start_seconds
        for segment in transcript.response.get("segments") or []:
            adjusted = dict(segment)
            if "start" in adjusted and adjusted["start"] is not None:
                adjusted["start"] = float(adjusted["start"]) + offset
            if "end" in adjusted and adjusted["end"] is not None:
                adjusted["end"] = float(adjusted["end"]) + offset
            adjusted["chunk_index"] = transcript.chunk.index
            merged.append(adjusted)
    return merged


def build_clean_markdown(raw_payload: dict[str, Any]) -> str:
    lines = [
        "# Transcript",
        "",
        f"- Source: `{Path(raw_payload['source']).name}`",
        f"- Model: `{raw_payload['model']}`",
        f"- Diarization: {'enabled' if raw_payload['diarize'] else 'disabled'}",
        "",
    ]

    if raw_payload["diarize"] and raw_payload.get("segments"):
        lines.extend(_speaker_markdown(raw_payload["segments"]))
    else:
        lines.extend(_plain_markdown(raw_payload))

    return "\n".join(lines).rstrip() + "\n"


def _speaker_markdown(segments: list[dict[str, Any]]) -> list[str]:
    lines = ["## Speaker-Labeled Transcript", ""]
    for segment in segments:
        speaker = str(segment.get("speaker") or "Unknown").strip()
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start = format_timestamp(segment.get("start"))
        end = format_timestamp(segment.get("end"))
        lines.append(f"**Speaker {speaker}** `{start} - {end}`")
        lines.append("")
        lines.append(text)
        lines.append("")
    return lines


def _plain_markdown(raw_payload: dict[str, Any]) -> list[str]:
    chunks = raw_payload.get("chunks") or []
    if len(chunks) <= 1:
        text = str(raw_payload.get("text") or "").strip()
        return ["## Transcript", "", text, ""] if text else ["## Transcript", "", ""]

    lines = ["## Transcript", ""]
    for chunk in chunks:
        text = str((chunk.get("response") or {}).get("text") or "").strip()
        if not text:
            continue
        start = format_timestamp(chunk.get("start_seconds"))
        end = format_timestamp(chunk.get("end_seconds"))
        lines.append(f"### Chunk {chunk['index']} `{start} - {end}`")
        lines.append("")
        lines.append(text)
        lines.append("")
    return lines
