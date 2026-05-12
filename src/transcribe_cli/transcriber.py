from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from transcribe_cli.chunker import Chunk
from transcribe_cli.config import DIARIZE_MODEL
from transcribe_cli.logging_utils import log


@dataclass(frozen=True)
class ChunkTranscript:
    chunk: Chunk
    response: dict[str, Any]


def transcribe_chunks(
    chunks: list[Chunk],
    model: str,
    language: str | None,
    prompt: str | None,
    diarize: bool,
) -> list[ChunkTranscript]:
    client = OpenAI()
    results: list[ChunkTranscript] = []
    total = len(chunks)

    for chunk in chunks:
        log(f"transcribing chunk {chunk.index}/{total}: {chunk.path.name}")
        response = transcribe_chunk_with_retries(
            client=client,
            chunk_path=chunk.path,
            model=model,
            language=language,
            prompt=prompt,
            diarize=diarize,
        )
        results.append(ChunkTranscript(chunk=chunk, response=response))

    return results


def transcribe_chunk_with_retries(
    client: OpenAI,
    chunk_path: Path,
    model: str,
    language: str | None,
    prompt: str | None,
    diarize: bool,
    max_attempts: int = 5,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return _transcribe_once(
                client=client,
                chunk_path=chunk_path,
                model=model,
                language=language,
                prompt=prompt,
                diarize=diarize,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc
        except APIStatusError as exc:
            if exc.status_code < 500 and exc.status_code not in {408, 409, 429}:
                raise
            last_error = exc

        if attempt < max_attempts:
            delay = min(60.0, (2 ** (attempt - 1)) + random.uniform(0.0, 0.75))
            log(f"transcription attempt {attempt} failed; retrying in {delay:.1f}s")
            time.sleep(delay)

    raise RuntimeError(f"Transcription failed after {max_attempts} attempts: {last_error}") from last_error


def _transcribe_once(
    client: OpenAI,
    chunk_path: Path,
    model: str,
    language: str | None,
    prompt: str | None,
    diarize: bool,
) -> dict[str, Any]:
    response_format = "diarized_json" if diarize else "json"
    params: dict[str, Any] = {
        "model": model,
        "response_format": response_format,
    }

    if language:
        params["language"] = language
    if prompt and not diarize:
        params["prompt"] = prompt
    if diarize:
        params["chunking_strategy"] = "auto"
        if model != DIARIZE_MODEL:
            raise ValueError(f"Diarization requires {DIARIZE_MODEL}.")

    with chunk_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(file=audio_file, **params)

    return _response_to_dict(response)


def _response_to_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, str):
        return {"text": response}
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "to_dict"):
        return response.to_dict()
    if isinstance(response, dict):
        return response
    return {"text": str(response)}
