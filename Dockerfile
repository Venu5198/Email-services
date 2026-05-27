# =============================================================================
# SyncRivo Email Service — FastAPI Backend
# Multi-Stage Dockerfile
#
# Stage 1 (builder): Installs all Python deps into a virtual environment
# Stage 2 (runtime): Lean production image — only copies the venv + app code
# =============================================================================

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools needed by some Python packages (e.g. cryptography, lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (leverages Docker layer cache)
COPY requirements.txt .

# Create an isolated venv and install all dependencies into it
RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /venv/bin/pip install --no-cache-dir apscheduler==3.10.4

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="SyncRivo Team"
LABEL description="SyncRivo Centralized Email Service — FastAPI Backend"
LABEL version="2.0"

# Create a non-root user for security
RUN groupadd -r syncrivo && useradd -r -g syncrivo -d /app -s /sbin/nologin syncrivo

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /venv /venv

# Copy application source code
COPY app/ ./app/
COPY syncrivo_email_sdk/ ./syncrivo_email_sdk/

# Create directories the app writes to at runtime
RUN mkdir -p /app/app/templates /app/uploads && \
    chown -R syncrivo:syncrivo /app

# Switch to non-root user
USER syncrivo

# Activate the venv by putting it first on PATH
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000

# Healthcheck — polls /health every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start Uvicorn with production-tuned settings
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "asyncio", \
     "--log-level", "info", \
     "--access-log"]
