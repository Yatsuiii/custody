"""One thin call into Vertex AI, with the cost of it recorded.

The SDK import is deferred so the rest of the benchmark, and every test that
exercises it, runs with nothing installed. Temperature is pinned at zero for
both systems: the comparison should not turn on sampling luck, and the baseline
deserves its best shot.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_LOCATION = "global"


@dataclass(frozen=True, slots=True)
class Call:
    text: str
    prompt_tokens: int
    output_tokens: int
    seconds: float
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "seconds": round(self.seconds, 3),
            "error": self.error,
        }


class Gemini:
    def __init__(
        self, project: str, location: str = DEFAULT_LOCATION,
        model: str = DEFAULT_MODEL,
    ) -> None:
        from google import genai  # noqa: PLC0415

        self.model = model
        self.project = project
        self.location = location
        self._client = genai.Client(vertexai=True, project=project,
                                    location=location)

    def ask(self, prompt: str, schema: dict) -> Call:
        from google.genai import types  # noqa: PLC0415

        started = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as failure:  # noqa: BLE001
            return Call("", 0, 0, time.monotonic() - started, repr(failure)[:300])
        usage = response.usage_metadata
        return Call(
            response.text or "",
            usage.prompt_token_count or 0,
            (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
            time.monotonic() - started,
        )

    def describe(self) -> dict:
        return {"model": self.model, "project": self.project,
                "location": self.location, "api": "Vertex AI via google-genai"}
