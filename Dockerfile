# ============================================================
# Justice_system — Dockerfile
# Multi-stage: builds frontend (Node) + backend (Python)
# Single container serves both via Nitro SSR proxy
# ============================================================

# ── Stage 1: Build frontend ──
FROM node:22-slim AS frontend-builder

WORKDIR /build
COPY frontend/ .
RUN npm ci && npm run build

# ── Stage 2: Install Python deps ──
FROM python:3.11-slim AS python-builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 3: Final runtime ──
FROM python:3.11-slim

# Install Node.js for Nitro SSR server
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user and data directories
RUN useradd -m -u 1000 justice && \
    mkdir -p /data /logs /uploads /docs/legal && \
    chown -R justice:justice /data /logs /uploads

# Copy Python dependencies from builder
COPY --from=python-builder /root/.local /home/justice/.local

# Copy built frontend
COPY --from=frontend-builder /build/dist /app/frontend/dist
COPY --from=frontend-builder /build/package.json /app/frontend/

# Copy application code
COPY --chown=justice:justice src/ /app/src/
COPY --chown=justice:justice docs/ /app/docs/
COPY --chown=justice:justice .env.example /app/.env

# Copy entrypoint
COPY --chown=justice:justice scripts/docker-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH=/home/justice/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    LEGAL_DIR=/app/docs/legal \
    LOG_FILE=/logs/justice.log \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app
USER justice

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
