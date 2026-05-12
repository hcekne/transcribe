FROM python:3.12-slim

ARG USER_NAME=appuser
ARG USER_ID=1000
ARG GROUP_ID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        ffmpeg \
        git \
        make \
        sudo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY tests /app/tests
COPY transcribe.py /app/transcribe.py

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[dev]"

RUN if getent group "${GROUP_ID}" >/dev/null; then \
        GROUP_NAME="$(getent group "${GROUP_ID}" | cut -d: -f1)"; \
    else \
        groupadd --gid "${GROUP_ID}" "${USER_NAME}"; \
        GROUP_NAME="${USER_NAME}"; \
    fi \
    && useradd --uid "${USER_ID}" --gid "${GROUP_ID}" --create-home --shell /bin/bash "${USER_NAME}" \
    && usermod -aG sudo "${USER_NAME}" \
    && echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USER_NAME}" \
    && chmod 0440 "/etc/sudoers.d/${USER_NAME}" \
    && mkdir -p /data/input /data/output \
    && chown -R "${USER_ID}:${GROUP_ID}" /app /data

USER "${USER_NAME}"

ENTRYPOINT ["transcribe"]
CMD ["--help"]
