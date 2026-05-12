from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AudioToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioMetadata:
    duration_seconds: float
    size_bytes: int


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        command = " ".join(args)
        details = result.stderr.strip() or result.stdout.strip()
        raise AudioToolError(f"Command failed: {command}\n{details}")
    return result


def probe_audio(path: Path) -> AudioMetadata:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration") or 0)
    return AudioMetadata(duration_seconds=duration, size_bytes=path.stat().st_size)


def convert_to_aac_m4a(source: Path, destination: Path, bitrate: str = "80k") -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "32000",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return destination


def extract_audio_segment(source: Path, destination: Path, start: float, end: float) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end - start)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-acodec",
            "copy",
            str(destination),
        ]
    )
    return destination
