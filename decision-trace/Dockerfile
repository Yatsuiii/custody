FROM python:3.13-slim

WORKDIR /workspace

COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY vertex.py gh_util.py ./
COPY data/decisions.jsonl ./data/decisions.jsonl
COPY app/ ./app/
COPY .streamlit/ ./.streamlit/

ENV PYTHONUNBUFFERED=1

# Cloud Run injects PORT; default 8080 for local `docker run`.
CMD ["sh", "-c", "streamlit run app/ui.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless true"]
