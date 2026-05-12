from __future__ import annotations


def format_timestamp(seconds: float | int | None) -> str:
    if seconds is None:
        return "00:00:00"
    total_seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
