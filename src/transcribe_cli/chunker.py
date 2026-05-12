from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from transcribe_cli.audio import extract_audio_segment, probe_audio
from transcribe_cli.logging_utils import log

SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<start>[0-9.]+)")
SILENCE_END_RE = re.compile(
    r"silence_end:\s*(?P<end>[0-9.]+)\s*\|\s*silence_duration:\s*(?P<duration>[0-9.]+)"
)


@dataclass(frozen=True)
class SilenceRange:
    start: float
    end: float

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2


@dataclass(frozen=True)
class Chunk:
    index: int
    path: Path
    start_seconds: float
    end_seconds: float

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size


def detect_silences(path: Path, noise_threshold: str = "-35dB", min_duration: float = 0.75) -> list[SilenceRange]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_threshold}:d={min_duration}",
            "-f",
            "null",
            "-",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = "\n".join([result.stdout, result.stderr])
    starts: list[float] = []
    ranges: list[SilenceRange] = []

    for line in output.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            starts.append(float(start_match.group("start")))
            continue

        end_match = SILENCE_END_RE.search(line)
        if end_match:
            end = float(end_match.group("end"))
            duration = float(end_match.group("duration"))
            start = starts.pop(0) if starts else max(0.0, end - duration)
            if end > start:
                ranges.append(SilenceRange(start=start, end=end))

    return ranges


def plan_chunk_boundaries(
    duration_seconds: float,
    source_size_bytes: int,
    target_bytes: int,
    silences: list[SilenceRange],
) -> list[tuple[float, float]]:
    if source_size_bytes <= target_bytes or duration_seconds <= 0:
        return [(0.0, max(0.1, duration_seconds))]

    bytes_per_second = source_size_bytes / duration_seconds
    max_duration = max(30.0, (target_bytes / bytes_per_second) * 0.95)
    min_useful_duration = min(max_duration * 0.5, max(30.0, max_duration - 120.0))

    boundaries: list[tuple[float, float]] = []
    start = 0.0
    while start < duration_seconds - 0.1:
        ideal_end = min(duration_seconds, start + max_duration)
        if ideal_end >= duration_seconds:
            boundaries.append((start, duration_seconds))
            break

        lower_bound = start + min_useful_duration
        candidates = [
            silence.midpoint
            for silence in silences
            if lower_bound <= silence.midpoint <= ideal_end
        ]
        if not candidates:
            candidates = [
                silence.midpoint
                for silence in silences
                if start + 5.0 <= silence.midpoint <= ideal_end
            ]

        end = max(candidates) if candidates else ideal_end
        if end <= start + 1.0:
            end = min(duration_seconds, start + max_duration)

        boundaries.append((start, end))
        start = end

    return boundaries


def create_chunks(source: Path, chunks_dir: Path, target_bytes: int) -> list[Chunk]:
    metadata = probe_audio(source)
    if metadata.size_bytes <= target_bytes:
        chunk_path = chunks_dir / "chunk_0001.m4a"
        extract_audio_segment(source, chunk_path, 0.0, metadata.duration_seconds)
        return [Chunk(index=1, path=chunk_path, start_seconds=0.0, end_seconds=metadata.duration_seconds)]

    log("detecting silence for chunk boundaries")
    silences = detect_silences(source)
    if silences:
        log(f"found {len(silences)} silence ranges")
    else:
        log("no silence ranges found; falling back to duration-based chunking")

    planned = plan_chunk_boundaries(
        duration_seconds=metadata.duration_seconds,
        source_size_bytes=metadata.size_bytes,
        target_bytes=target_bytes,
        silences=silences,
    )

    chunks = _write_planned_chunks(source, chunks_dir, planned)
    return ensure_chunks_under_limit(chunks, target_bytes, chunks_dir)


def _write_planned_chunks(source: Path, chunks_dir: Path, planned: list[tuple[float, float]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for index, (start, end) in enumerate(planned, start=1):
        chunk_path = chunks_dir / f"chunk_{index:04d}.m4a"
        extract_audio_segment(source, chunk_path, start, end)
        chunks.append(Chunk(index=index, path=chunk_path, start_seconds=start, end_seconds=end))
    return chunks


def ensure_chunks_under_limit(chunks: list[Chunk], target_bytes: int, chunks_dir: Path) -> list[Chunk]:
    output: list[Chunk] = []
    for chunk in chunks:
        if chunk.size_bytes <= target_bytes:
            output.append(chunk)
            continue

        log(
            f"{chunk.path.name} is {chunk.size_bytes / 1024 / 1024:.1f} MB; "
            "splitting it recursively"
        )
        output.extend(_split_oversized_chunk(chunk, target_bytes, chunks_dir, depth=0))

    renumbered: list[Chunk] = []
    for index, chunk in enumerate(output, start=1):
        renumbered.append(
            Chunk(index=index, path=chunk.path, start_seconds=chunk.start_seconds, end_seconds=chunk.end_seconds)
        )
    return renumbered


def _split_oversized_chunk(chunk: Chunk, target_bytes: int, chunks_dir: Path, depth: int) -> list[Chunk]:
    if chunk.size_bytes <= target_bytes:
        return [chunk]
    if depth > 10:
        raise RuntimeError(f"Unable to split {chunk.path} below the target upload size.")

    duration = max(0.1, chunk.end_seconds - chunk.start_seconds)
    local_silences = detect_silences(chunk.path)
    midpoint = duration / 2
    cut_local = _nearest_silence_to_midpoint(local_silences, midpoint) or midpoint
    cut_absolute = chunk.start_seconds + cut_local

    if cut_absolute <= chunk.start_seconds + 0.5 or cut_absolute >= chunk.end_seconds - 0.5:
        cut_absolute = chunk.start_seconds + midpoint

    left_path = chunks_dir / f"{chunk.path.stem}_a.m4a"
    right_path = chunks_dir / f"{chunk.path.stem}_b.m4a"
    extract_audio_segment(chunk.path, left_path, 0.0, cut_local)
    extract_audio_segment(chunk.path, right_path, cut_local, duration)

    left = Chunk(index=chunk.index, path=left_path, start_seconds=chunk.start_seconds, end_seconds=cut_absolute)
    right = Chunk(index=chunk.index, path=right_path, start_seconds=cut_absolute, end_seconds=chunk.end_seconds)

    return [
        *_split_oversized_chunk(left, target_bytes, chunks_dir, depth + 1),
        *_split_oversized_chunk(right, target_bytes, chunks_dir, depth + 1),
    ]


def _nearest_silence_to_midpoint(silences: list[SilenceRange], midpoint: float) -> float | None:
    if not silences:
        return None
    return min(silences, key=lambda silence: abs(silence.midpoint - midpoint)).midpoint
