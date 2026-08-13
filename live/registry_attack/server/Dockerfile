FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    CUSTODY_MCP_REVISION=v1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
        -r requirements.txt \
    && python -m pip check

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser
COPY --chown=appuser:appuser server.py ./
# R2's dispatch attestation is server.py's own logic reused, not
# reimplemented: custody/revision.py is pure stdlib, no extra pip
# dependency, so it's cheap to vendor into this otherwise-standalone image.
# Cloud Build's context is this directory, not the repo root, so the caller
# (scripts/live_revision_binding.py) copies custody/{__init__,origin,
# revision}.py into ./custody/ here before `gcloud builds submit` runs.
COPY --chown=appuser:appuser custody ./custody

USER 10001
EXPOSE 8080

CMD ["python", "server.py"]
