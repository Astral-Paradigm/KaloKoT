# ============================================================
# Justice_system — Dockerfile
# Multi-stage: build deps, then slim runtime
# ============================================================

FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

RUN useradd -m -u 1000 justice && \
    mkdir -p /data /logs /uploads /docs/legal && \
    chown -R justice:justice /data /logs /uploads

COPY --from=builder /root/.local /home/justice/.local
COPY --chown=justice:justice src/ /app/src/
COPY --chown=justice:justice docs/ /app/docs/
COPY --chown=justice:justice .env.example /app/.env

ENV PATH=/home/justice/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    LEGAL_DIR=/app/docs/legal \
    LOG_FILE=/logs/justice.log \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app
USER justice

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python3", "src/main.py", "--api"]
