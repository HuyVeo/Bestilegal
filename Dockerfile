# ── Stage 1: Frontend build ──────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build


# ── Stage 2: Python builder ──────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install project with all optional extras
COPY src/ src/
RUN uv sync --frozen --no-dev --extra prod --extra anthropic --extra redis


# ── Stage 3: Runtime ──────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --no-create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv .venv/

# Copy application files (least → most frequently changed)
COPY sql/ sql/
COPY static/ static/
COPY --from=frontend /static/ static/
COPY src/ src/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["uvicorn", \
     "chatbot_viva.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--workers", "2", \
     "--timeout-keep-alive", "120", \
     "--access-log", \
     "--log-level", "info"]
