from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-4o-transcribe"
DIARIZE_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_OUTPUT_DIR = Path("/data/output")
TARGET_CHUNK_MB = 24
TARGET_CHUNK_BYTES = TARGET_CHUNK_MB * 1024 * 1024


@dataclass(frozen=True)
class RuntimeConfig:
    model: str
    diarize: bool
    api_key: str


def load_environment() -> None:
    """Load .env from the current working directory when present."""
    load_dotenv()


def resolve_model(model_arg: str | None, diarize_requested: bool) -> tuple[str, bool, str | None]:
    env_model = os.getenv("OPENAI_TRANSCRIBE_MODEL")
    explicit_model = model_arg is not None
    model = model_arg or env_model or DEFAULT_MODEL
    warning = None

    if diarize_requested:
        if explicit_model and model != DIARIZE_MODEL:
            raise ValueError(f"--diarize requires --model {DIARIZE_MODEL}; got {model!r}.")
        if model != DIARIZE_MODEL:
            if env_model and env_model != DIARIZE_MODEL:
                warning = (
                    f"--diarize requested; ignoring OPENAI_TRANSCRIBE_MODEL={env_model!r} "
                    f"and using {DIARIZE_MODEL!r}."
                )
            model = DIARIZE_MODEL

    diarize = diarize_requested or model == DIARIZE_MODEL
    return model, diarize, warning


def require_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to .env or export it in your shell.")
    return api_key
