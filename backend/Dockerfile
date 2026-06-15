# ══════════════════════════════════════════════════════════════════
# Stage 1: Builder
# Install all dependencies including build tools.
# This stage is NOT in the final image — keeps it small.
# ══════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS builder

WORKDIR /build

# System packages needed to compile some Python packages
# Note: libgdk-pixbuf-xlib-2.0-0 replaces libgdk-pixbuf2.0-0 in Debian Trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages into /install (we'll copy this to final image)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ══════════════════════════════════════════════════════════════════
# Stage 2: Final image
# Only runtime dependencies — no gcc, no build tools.
# ══════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS final

WORKDIR /app

# Runtime system packages only
# Note: libgdk-pixbuf-xlib-2.0-0 replaces libgdk-pixbuf2.0-0 in Debian Trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/

# ── Security: non-root user ───────────────────────────────────────
RUN useradd -m -u 1001 -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# ── Environment defaults ──────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000

EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Start command ─────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--log-level", "info"]
