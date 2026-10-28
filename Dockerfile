# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    ENGLISH_TEACHER_HOST=0.0.0.0 \
    ENGLISH_TEACHER_PORT=8000 \
    ENGLISH_TEACHER_DB=/data/sessions.sqlite \
    ENGLISH_TEACHER_EVENTS_DB=/data/events.sqlite \
    ENGLISH_TEACHER_KILL_SWITCH_FILE=/data/kill-switch.json

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.29

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /app /data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

CMD ["/app/.venv/bin/english-teacher-web"]
