#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT_DIR="${ROOT_DIR}/input"
OUTPUT_DIR="${ROOT_DIR}/output"
PROCESSED_DIR="${ROOT_DIR}/processed"

mkdir -p "${INPUT_DIR}" "${OUTPUT_DIR}" "${PROCESSED_DIR}"

is_supported_extension() {
  local extension="$1"
  local supported="$2"
  local candidate

  for candidate in ${supported}; do
    if [ "${extension}" = "${candidate}" ]; then
      return 0
    fi
  done

  return 1
}

safe_name() {
  local raw="$1"
  local sanitized
  sanitized="$(printf '%s' "${raw}" | tr -c 'A-Za-z0-9._-' '_' | sed 's/^_*//; s/_*$//')"

  if [ -z "${sanitized}" ]; then
    sanitized="audio"
  fi

  printf '%s' "${sanitized}"
}

unique_path() {
  local path="$1"
  local stem extension candidate counter timestamp

  if [ ! -e "${path}" ]; then
    printf '%s' "${path}"
    return 0
  fi

  timestamp="$(date +%Y%m%d_%H%M%S)"

  if [ -f "${path}" ] && [ "${path##*/}" != "${path##*.}" ]; then
    stem="${path%.*}"
    extension=".${path##*.}"
  else
    stem="${path}"
    extension=""
  fi

  counter=1
  while true; do
    if [ "${counter}" -eq 1 ]; then
      candidate="${stem}_${timestamp}${extension}"
    else
      candidate="${stem}_${timestamp}_${counter}${extension}"
    fi

    if [ ! -e "${candidate}" ]; then
      printf '%s' "${candidate}"
      return 0
    fi

    counter=$((counter + 1))
  done
}

if [ ! -f "${ROOT_DIR}/.env" ]; then
  touch "${ROOT_DIR}/.env"
  echo "Created ${ROOT_DIR}/.env. Add OPENAI_API_KEY before running real transcriptions." >&2
fi

if ! grep -Eq '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=[[:space:]]*.+$' "${ROOT_DIR}/.env" \
  && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set. Add it to .env or export it before running." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is installed." >&2
  exit 127
fi

export USER_ID="${USER_ID:-$(id -u)}"
export GROUP_ID="${GROUP_ID:-$(id -g)}"
export USER_NAME="${USER_NAME:-$(id -un 2>/dev/null || echo appuser)}"

if [ "${TRANSCRIBE_SKIP_BUILD:-0}" != "1" ]; then
  "${COMPOSE_CMD[@]}" build transcribe
fi

supported_extensions="m4a aif aifc aiff wav mp3 mp4 mpeg mpga webm flac ogg oga"
found=0
processed=0
failed=0

shopt -s nullglob
for source_path in "${INPUT_DIR}"/*; do
  [ -f "${source_path}" ] || continue

  base_name="$(basename "${source_path}")"
  extension="${base_name##*.}"
  extension_lower="$(printf '%s' "${extension}" | tr '[:upper:]' '[:lower:]')"

  if ! is_supported_extension "${extension_lower}" "${supported_extensions}"; then
    echo "Skipping unsupported file: ${base_name}" >&2
    continue
  fi

  found=1
  stem="${base_name%.*}"
  safe_stem="$(safe_name "${stem}")"
  output_subdir="$(unique_path "${OUTPUT_DIR}/${safe_stem}")"
  processed_path="$(unique_path "${PROCESSED_DIR}/${base_name}")"

  mkdir -p "${output_subdir}"

  echo
  echo "Transcribing: ${base_name}"
  echo "Output: ${output_subdir}"

  if "${COMPOSE_CMD[@]}" run --rm transcribe \
    "/data/input/${base_name}" \
    --output-dir "/data/output/$(basename "${output_subdir}")" \
    "$@"; then
    mv "${source_path}" "${processed_path}"
    echo "Moved processed audio to: ${processed_path}"
    processed=$((processed + 1))
  else
    echo "Failed: ${base_name}" >&2
    failed=$((failed + 1))
  fi
done
shopt -u nullglob

if [ "${found}" -eq 0 ]; then
  echo "No supported audio files found in ${INPUT_DIR}."
  exit 0
fi

echo
echo "Batch complete: ${processed} processed, ${failed} failed."

if [ "${failed}" -gt 0 ]; then
  exit 1
fi
