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
# Probe the port the server was actually told to bind. Hardcoding 8080 here while the
# command honours $PORT reports a healthy container as unhealthy the moment they differ.
HEALTHCHECK --interval=30s --timeout=4s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8080')}/healthz\", timeout=3).status==200 else 1)"

# exec, so uvicorn replaces the shell and becomes PID 1. Without it the shell holds PID 1
# and SIGTERM never reaches the server, so shutdown waits out the runtime's kill timeout.
# --proxy-headers lets the app see the browser's real scheme behind a TLS-terminating
# proxy, which is what decides whether the session cookie is marked Secure. The container
# is only reachable through that proxy, so trusting its forwarded headers is sound.
CMD ["sh", "-c", "exec uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
