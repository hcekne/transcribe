from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from transcribe_cli.audio import convert_to_aac_m4a, probe_audio
from transcribe_cli.chunker import create_chunks
from transcribe_cli.config import DEFAULT_OUTPUT_DIR, TARGET_CHUNK_BYTES, load_environment, require_api_key, resolve_model
from transcribe_cli.logging_utils import log
from transcribe_cli.output import write_outputs
from transcribe_cli.transcriber import transcribe_chunks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Convert, chunk, and transcribe audio with OpenAI speech-to-text models.",
    )
    parser.add_argument("audio_file", nargs="?", type=Path, help="Path to the audio file to transcribe.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for transcript outputs.")
    parser.add_argument("--model", help="OpenAI transcription model. Defaults to OPENAI_TRANSCRIBE_MODEL or gpt-4o-transcribe.")
    parser.add_argument("--language", help="Optional input language hint, such as en or es.")
    parser.add_argument("--diarize", action="store_true", help="Enable speaker-labeled transcription.")
    parser.add_argument("--keep-chunks", action="store_true", help="Keep normalized audio and generated chunk files.")
    parser.add_argument("--prompt", help="Optional transcription prompt. Ignored for diarization models.")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_environment()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.audio_file is None:
        parser.print_help()
        return 0

    try:
        run(args)
    except Exception as exc:
        log(f"error: {exc}")
        return 1
    return 0


def run(args: argparse.Namespace) -> None:
    source = args.audio_file.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Input audio file not found: {source}")

    model, diarize, model_warning = resolve_model(args.model, args.diarize)
    if model_warning:
        log(model_warning)
    if diarize and args.prompt:
        log("prompt is not supported for diarized transcription; ignoring --prompt")
    require_api_key()

    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = _prepare_workspace(output_dir, source, args.keep_chunks)

    try:
        normalized_path = workspace / f"{source.stem}.normalized.m4a"
        log(f"conversion: {source.name} -> {normalized_path.name}")
        convert_to_aac_m4a(source, normalized_path)
        metadata = probe_audio(normalized_path)
        log(
            f"normalized audio: {metadata.duration_seconds:.1f}s, "
            f"{metadata.size_bytes / 1024 / 1024:.1f} MB"
        )

        chunks_dir = workspace / "chunks"
        log("chunking audio")
        chunks = create_chunks(normalized_path, chunks_dir, TARGET_CHUNK_BYTES)
        log(f"prepared {len(chunks)} chunk(s)")
        for chunk in chunks:
            log(
                f"chunk {chunk.index}: {chunk.start_seconds:.1f}s-{chunk.end_seconds:.1f}s, "
                f"{chunk.size_bytes / 1024 / 1024:.1f} MB"
            )

        transcripts = transcribe_chunks(
            chunks=chunks,
            model=model,
            language=args.language,
            prompt=None if diarize else args.prompt,
            diarize=diarize,
        )

        log("merging transcripts")
        clean_path, raw_path = write_outputs(
            output_dir=output_dir,
            source_path=source,
            normalized_path=normalized_path,
            model=model,
            language=args.language,
            diarize=diarize,
            target_chunk_bytes=TARGET_CHUNK_BYTES,
            transcripts=transcripts,
        )
        log(f"writing output: {clean_path}")
        log(f"writing output: {raw_path}")
    finally:
        if not args.keep_chunks:
            shutil.rmtree(workspace, ignore_errors=True)
        else:
            log(f"kept intermediate files in {workspace}")


def _prepare_workspace(output_dir: Path, source: Path, keep_chunks: bool) -> Path:
    if keep_chunks:
        workspace = output_dir / "chunks" / source.stem
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    return Path(tempfile.mkdtemp(prefix=f"{source.stem}-", dir=output_dir))
