#!/usr/bin/env bash
set -euo pipefail

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"
USER_NAME="${USER:-appuser}"

export USER_ID
export GROUP_ID
export USER_NAME

mkdir -p input output

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is installed." >&2
  exit 127
fi

echo "User ID: ${USER_ID}"
echo "Group ID: ${GROUP_ID}"
echo "Username: ${USER_NAME}"

"${COMPOSE_CMD[@]}" up --build -d dev

echo "Development container started."
echo "Enter it with: docker exec -it transcribe-dev bash"
echo "Run tests with: ${COMPOSE_CMD[*]} exec -T dev pytest"
