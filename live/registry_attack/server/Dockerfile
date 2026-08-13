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

USER 10001
EXPOSE 8080

CMD ["python", "server.py"]
