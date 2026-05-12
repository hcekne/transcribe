# OpenAI Audio Transcribe

Dockerized Python 3.12 CLI for converting, chunking, and transcribing audio with the OpenAI API.

## Setup

Clone the repository and create the mounted host directories:

```bash
git clone git@github.com:hcekne/transcribe.git
cd transcribe
mkdir -p input output
```

Add your API key to `.env`:

```bash
OPENAI_API_KEY=sk-your-key-here
```

The committed `.env` file starts empty so secrets are not hardcoded. You can also export the key in your shell instead.

## Build

```bash
docker compose build
```

For Linux hosts where output file ownership matters, build with your host UID and GID:

```bash
USER_ID=$(id -u) GROUP_ID=$(id -g) USER_NAME=$(whoami) docker compose build
```

You can also start the persistent development container:

```bash
bash start_container.sh
docker exec -it transcribe-dev bash
```

Inside the development container, run project commands from `/app`.

## Self-Test

```bash
docker compose run --rm transcribe --help
```

Or inside the dev container:

```bash
pytest
```

## Run

Put audio files in `./input`. Outputs are written to `./output`:

```bash
docker compose run --rm transcribe /data/input/interview.m4a
```

With explicit options:

```bash
docker compose run --rm transcribe \
  /data/input/interview.aifc \
  --output-dir /data/output \
  --model gpt-4o-transcribe-diarize \
  --diarize
```

Other useful flags:

```bash
docker compose run --rm transcribe /data/input/interview.mp3 \
  --language en \
  --prompt "Interview about product strategy and AI." \
  --keep-chunks
```

The CLI produces:

- `output/transcript_clean.md`
- `output/transcript_raw.json`

When `--diarize` is enabled, Markdown output uses speaker labels when the API returns speaker segments.

## How It Works

The CLI first converts the input to speech-oriented AAC in an `.m4a` container using ffmpeg:

- mono audio
- 32 kHz sample rate
- 80 kbps AAC
- no video stream

It then checks the normalized file size against a 24 MB target, leaving a margin under the 25 MB OpenAI upload limit. If the file is larger, ffmpeg `silencedetect` finds quiet ranges and the chunk planner chooses split points near silence before the estimated size limit. If a chunk still lands above 24 MB, it is split recursively until all upload files are under the target.

Chunks are sent in order to the OpenAI transcription endpoint. The default model is `gpt-4o-transcribe`, configurable with `OPENAI_TRANSCRIBE_MODEL` or `--model`. Diarization uses `gpt-4o-transcribe-diarize`, `response_format=diarized_json`, and `chunking_strategy=auto`.

API calls use exponential backoff for transient connection, timeout, rate-limit, and server errors. Raw per-chunk API responses and adjusted merged diarization segments are stored in `transcript_raw.json`.

## macOS

The Docker image uses `python:3.12-slim` and installs ffmpeg with apt, so it works on Apple Silicon through Docker Desktop without macOS-specific binaries or paths.

Typical macOS use:

```bash
docker compose build
docker compose run --rm transcribe /data/input/interview.m4a
```

## Linux

On Linux, run with your UID/GID to keep mounted output files owned by your host user:

```bash
USER_ID=$(id -u) GROUP_ID=$(id -g) USER_NAME=$(whoami) docker compose run --rm transcribe /data/input/interview.wav
```

The `start_container.sh` helper exports those values automatically for the dev container.

## ARM64 vs AMD64

The project uses the official multi-arch `python:3.12-slim` image and Debian ffmpeg packages. No architecture-specific binaries are downloaded.

You normally do not need to pin a platform. If you need to force one manually:

```bash
docker compose build --build-arg USER_ID=$(id -u) --build-arg GROUP_ID=$(id -g)
docker run --platform linux/amd64 --rm openai-audio-transcribe:dev --help
docker run --platform linux/arm64 --rm openai-audio-transcribe:dev --help
```

Optional buildx examples:

```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t openai-audio-transcribe:latest .
```

## Configuration

`.env` is loaded by Docker Compose and by the Python CLI:

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe
```

Supported CLI flags:

- `--output-dir`
- `--model`
- `--language`
- `--diarize`
- `--keep-chunks`
- `--prompt`

## Known Limitations

- Diarization may not perfectly identify speakers.
- Chunk boundaries can lose some context even when silence-aware splitting is used.
- Transcription cost depends on the selected model and audio length.
- Sensitive audio is sent to the OpenAI API.
