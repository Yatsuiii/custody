"""A transport that lets AutomationBench drive Gemini 3.x over Vertex.

Written only because every off-the-shelf path is closed: Vertex's
OpenAI-compatible endpoint drops the thought signatures Gemini 3.x requires for
multi-turn tool calls, the benchmark's own Gemini client speaks an Interactions
input shape the Developer API has since replaced, and the free Developer tier
allows twenty requests a day against a benchmark that needs hundreds.

This sits at the transport boundary and nowhere else. It does not touch tasks,
tools, graders or the runner, so a score produced through it is still the
benchmark's own judgement of the model. It does put my code between the model
and the grader, which is a validity risk, and the mitigation is the `simple`
domain: two hundred foundational tool-use tasks where a correct transport should
score high and a broken one cannot.

The google-genai SDK is used rather than raw HTTP precisely because it
round-trips thought signatures itself, which is the thing that broke everywhere
else.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from google import genai
from google.genai import types
from verifiers.clients.client import Client
from verifiers.types import (
    AssistantMessage,
    ClientConfig,
    Messages,
    Response,
    ResponseMessage,
    SystemMessage,
    TextMessage,
    Tool,
    ToolCall,
    ToolMessage,
    Usage,
    UserMessage,
)

DEFAULT_PROJECT = os.environ.get("KEEL_VERTEX_PROJECT",
                                 "project-988bc9fe-092c-4b32-90c")
DEFAULT_LOCATION = os.environ.get("KEEL_VERTEX_LOCATION", "global")

# The benchmark's effort vocabulary is wider than Gemini's thinking levels.
# Anything without a mapping must fail loudly rather than silently downgrade,
# because a run at the wrong effort is not the run anyone asked for.
THINKING_LEVELS = {
    "minimal": "LOW",
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "xhigh": "HIGH",
    "max": "HIGH",
}


class VertexGeminiClient(Client[genai.Client, list, Any, dict]):
    """Vertex-backed Gemini transport for the AutomationBench runner."""

    # Gemini 3.x requires the thought signature it issued with a function call
    # to come back with that call on the next turn. vf's normalized transcript
    # does not carry it, so it is cached here by tool-call id and re-attached
    # when the turn is rebuilt. Without this, every second turn is a 400.
    _signatures: dict[str, bytes] = {}  # noqa: RUF012

    def setup_client(self, config: ClientConfig) -> genai.Client:
        return genai.Client(
            vertexai=True,
            project=os.environ.get("VERTEX_PROJECT", DEFAULT_PROJECT),
            location=os.environ.get("VERTEX_LOCATION", DEFAULT_LOCATION),
        )

    async def close(self) -> None:
        return None

    async def to_native_tool(self, tool: Tool) -> dict:
        return {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": _clean_schema(tool.parameters),
        }

    async def to_native_prompt(self, messages: Messages) -> tuple[list, dict]:
        """vf messages to Gemini contents, with the system prompt lifted out.

        Tool results must name the function they answer, which vf's ToolMessage
        does not carry, so the name is recovered from the call earlier in the
        transcript. A missing name is raised rather than guessed: a wrong name
        silently reshapes the conversation the model sees.
        """
        system: list[str] = []
        contents: list[types.Content] = []
        call_names: dict[str, str] = {}
        # Gemini requires one function-response part per function call in the
        # preceding model turn, all in a single content. vf emits one
        # ToolMessage per result, so consecutive results are buffered here and
        # flushed together; emitting them separately makes parallel tool calls
        # fail the arity check.
        pending: list[types.Part] = []

        def flush() -> None:
            if pending:
                contents.append(types.Content(role="user", parts=list(pending)))
                pending.clear()

        for msg in messages:
            if not isinstance(msg, ToolMessage):
                flush()
            if isinstance(msg, SystemMessage):
                system.append(_text_of(msg.content))
            elif isinstance(msg, UserMessage | TextMessage):
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=_text_of(msg.content))],
                ))
            elif isinstance(msg, AssistantMessage):
                contents.append(_model_turn(msg, call_names,
                                            self._signatures))
            elif isinstance(msg, ToolMessage):
                pending.append(_result_part(msg, call_names))

        flush()
        extra = {"system_instruction": "\n\n".join(system)} if system else {}
        return contents, extra

    @staticmethod
    def build_call_kwargs(prompt, model, sampling_args, tools=None, **kwargs):
        config: dict[str, Any] = {}
        if kwargs.get("system_instruction"):
            config["system_instruction"] = kwargs["system_instruction"]
        if tools:
            config["tools"] = [types.Tool(function_declarations=tools)]

        sa = dict(sampling_args or {})
        effort = sa.pop("reasoning_effort", None)
        if effort:
            if effort not in THINKING_LEVELS:
                raise ValueError(f"no Gemini thinking level for effort {effort!r}")
            config["thinking_config"] = types.ThinkingConfig(
                thinking_level=THINKING_LEVELS[effort]
            )
        for key in ("temperature", "seed", "max_tokens"):
            if sa.get(key) is not None:
                config["max_output_tokens" if key == "max_tokens" else key] = sa[key]

        return {"model": model, "contents": prompt,
                "config": types.GenerateContentConfig(**config)}

    async def get_native_response(self, prompt, model, sampling_args,
                                  tools=None, **kwargs):
        call = self.build_call_kwargs(prompt, model, sampling_args, tools,
                                      **kwargs)
        started = time.monotonic()
        response = await self.client.aio.models.generate_content(**call)
        return {"response": response, "model": model,
                "seconds": time.monotonic() - started}

    async def raise_from_native_response(self, response: Any) -> None:
        return None

    async def from_native_response(self, response: Any) -> Response:
        native = response["response"]
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for candidate in native.candidates or []:
            for part in (candidate.content.parts if candidate.content else []):
                if getattr(part, "text", None) and not getattr(
                        part, "thought", False):
                    text_parts.append(part.text)
                fn = getattr(part, "function_call", None)
                if fn is not None:
                    call_id = fn.id or f"call_{uuid.uuid4().hex[:12]}"
                    signature = getattr(part, "thought_signature", None)
                    if signature:
                        self._signatures[call_id] = signature
                    tool_calls.append(ToolCall(
                        id=call_id,
                        name=fn.name or "",
                        arguments=json.dumps(dict(fn.args or {})),
                    ))

        stop = str(getattr(
            (native.candidates or [None])[0], "finish_reason", "") or "")
        truncated = "MAX_TOKENS" in stop
        finish = "tool_calls" if tool_calls else ("length" if truncated
                                                 else "stop")
        meta = native.usage_metadata
        # Thinking tokens are reported separately and bill as output, so they
        # are counted in completion_tokens as well as recorded on their own.
        reasoning = getattr(meta, "thoughts_token_count", 0) or 0 if meta else 0
        usage = Usage(
            prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            reasoning_tokens=reasoning,
            completion_tokens=(getattr(meta, "candidates_token_count", 0) or 0)
            + reasoning,
            total_tokens=getattr(meta, "total_token_count", 0) or 0,
        ) if meta else None

        return Response(
            id=getattr(native, "response_id", None) or uuid.uuid4().hex,
            created=int(time.time()),
            model=response["model"],
            usage=usage,
            message=ResponseMessage(
                role="assistant",
                content="".join(text_parts),
                tool_calls=tool_calls or None,
                finish_reason=finish,
                is_truncated=truncated,
            ),
        )


def _model_turn(msg, call_names: dict[str, str],
                signatures: dict[str, bytes]) -> types.Content:
    parts: list[types.Part] = []
    if msg.content:
        parts.append(types.Part(text=_text_of(msg.content)))
    for call in msg.tool_calls or []:
        call_names[call.id] = call.name
        part = types.Part(function_call=types.FunctionCall(
            id=call.id, name=call.name,
            args=json.loads(call.arguments) if call.arguments else {},
        ))
        signature = signatures.get(call.id)
        if signature:
            part.thought_signature = signature
        parts.append(part)
    return types.Content(role="model", parts=parts)


def _result_part(msg, call_names: dict[str, str]) -> types.Part:
    """A tool result, refusing to guess the function it answers."""
    name = call_names.get(msg.tool_call_id)
    if name is None:
        raise ValueError(
            f"tool result {msg.tool_call_id!r} has no matching call earlier in "
            f"the transcript; known: {sorted(call_names)}"
        )
    return types.Part(function_response=types.FunctionResponse(
        id=msg.tool_call_id, name=name,
        response={"result": _text_of(msg.content)},
    ))


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    chunks = []
    for part in content or []:
        if hasattr(part, "text"):
            chunks.append(part.text)
        elif isinstance(part, dict) and part.get("type") == "text":
            chunks.append(part.get("text", ""))
    return "".join(chunks)


def _clean_schema(schema: Any) -> Any:
    """Drop JSON Schema keys Gemini's function declarations reject."""
    unsupported = {"additionalProperties", "$schema", "exclusiveMinimum",
                   "exclusiveMaximum", "const", "examples", "default"}
    if isinstance(schema, dict):
        return {k: _clean_schema(v) for k, v in schema.items()
                if k not in unsupported}
    if isinstance(schema, list):
        return [_clean_schema(v) for v in schema]
    return schema
