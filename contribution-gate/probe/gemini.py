"""One call into Vertex AI. Deliberately its own copy, not shared with the
other project in this repository: these are separate products that happen to
share a working directory, and a shared client would be the first thread that
ties them together."""

from __future__ import annotations

import time
from dataclasses import dataclass

DEFAULT_MODEL = "gemini-3.7-flash"
DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"


@dataclass(frozen=True, slots=True)
class Call:
    text: str
    prompt_tokens: int
    output_tokens: int
    seconds: float
    error: str = ""


class Gemini:
    def __init__(self, project: str = DEFAULT_PROJECT,
                 model: str = DEFAULT_MODEL) -> None:
        from google import genai  # noqa: PLC0415

        self.model = model
        self.project = project
        self._client = genai.Client(vertexai=True, project=project,
                                    location="global")

    def ask(self, prompt: str, schema: dict) -> Call:
        from google.genai import types  # noqa: PLC0415

        started = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0, response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as failure:  # noqa: BLE001
            return Call("", 0, 0, time.monotonic() - started,
                        repr(failure)[:200])
        usage = response.usage_metadata
        return Call(
            response.text or "", usage.prompt_token_count or 0,
            (usage.candidates_token_count or 0)
            + (usage.thoughts_token_count or 0),
            time.monotonic() - started,
        )

    def describe(self) -> dict:
        return {"model": self.model, "project": self.project,
                "api": "Vertex AI via google-genai"}
