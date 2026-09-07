# CAIRN situation room. Single-process by design: the run store is in-memory and
# per-session, so scaling out would split visitors across inconsistent state. Run one
# instance and let App Runner handle TLS and the public URL.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CAIRN_MODE=fixture \
    PORT=8080

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
COPY fixtures ./fixtures

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 cairn \
    && mkdir -p /srv/data && chown -R cairn:cairn /srv

USER cairn
EXPOSE 8080

# The demo runs on synthetic fixtures and needs no credentials; nothing here reads AWS
# configuration unless CAIRN_MODE is set to bedrock.
HEALTHCHECK --interval=30s --timeout=4s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
