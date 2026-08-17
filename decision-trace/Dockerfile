FROM python:3.13-slim

WORKDIR /workspace

# ingest.py shells out to the gh CLI (gh_util.py) for PR/search/content
# lookups; the base image has no gh binary, so live-ingest silently
# 404s ("No such file or directory: 'gh'") without this.
ARG GH_VERSION=2.63.2
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" -o /tmp/gh.tar.gz \
    && tar -xzf /tmp/gh.tar.gz -C /tmp \
    && mv "/tmp/gh_${GH_VERSION}_linux_amd64/bin/gh" /usr/local/bin/gh \
    && rm -rf /tmp/gh* \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY vertex.py gh_util.py ./
COPY data/decisions.jsonl ./data/decisions.jsonl
COPY app/ ./app/
COPY .streamlit/ ./.streamlit/

ENV PYTHONUNBUFFERED=1

# Cloud Run injects PORT; default 8080 for local `docker run`.
CMD ["sh", "-c", "streamlit run app/ui.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless true"]
