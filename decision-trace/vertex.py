"""Thin, standalone Vertex/Gemini helpers for the DecisionTrace v0 falsifier.

Not routed through AutomationBench's `verifiers` harness (this isn't an
AutomationBench task) — reuses the same project/credentials/transport
already validated in failure-mining/adapter/vertex_client.py.
"""

from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

PROJECT = os.environ.get("VERTEX_PROJECT", "project-988bc9fe-092c-4b32-90c")
GEN_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
EMBED_LOCATION = os.environ.get("VERTEX_EMBED_LOCATION", "us-central1")
GEN_MODEL = "gemini-3.7-flash"
EMBED_MODEL = "text-embedding-005"

# A prior run hung indefinitely on a network call with no timeout set (108
# minutes, 0% CPU, no exception raised — not a 429, nothing to retry on).
# http_options.timeout is milliseconds; 60s is generous for a single call.
_HTTP_OPTS = types.HttpOptions(timeout=60_000)

_gen_client = genai.Client(
    vertexai=True, project=PROJECT, location=GEN_LOCATION, http_options=_HTTP_OPTS
)
_embed_client = genai.Client(
    vertexai=True, project=PROJECT, location=EMBED_LOCATION, http_options=_HTTP_OPTS
)


def _with_backoff(fn, max_attempts: int = 6):
    delay = 5.0
    for attempt in range(max_attempts):
        try:
            return fn()
        except errors.ClientError as e:
            if e.code != 429 or attempt == max_attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception:
            # Includes timeouts from the 60s http_options cap above — retry
            # those too, since a hang looks identical to a slow transient.
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


def generate(prompt: str) -> str:
    r = _with_backoff(
        lambda: _gen_client.models.generate_content(model=GEN_MODEL, contents=prompt)
    )
    return r.text or ""


def embed(texts: list[str]) -> list[list[float]]:
    # Vertex embedding endpoints cap batch size; chunk conservatively.
    out: list[list[float]] = []
    batch = 5
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        r = _with_backoff(
            lambda chunk=chunk: _embed_client.models.embed_content(
                model=EMBED_MODEL, contents=chunk
            )
        )
        out.extend(e.values for e in r.embeddings)
        time.sleep(0.5)
    return out
