from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from litellm import acompletion, completion_cost

from utopiai.config import LLMProfile


@dataclass(frozen=True)
class LLMResult:
    content: str
    tool_calls: list[dict[str, Any]]
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    latency_ms: int


async def complete(
    profile: LLMProfile,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> LLMResult:
    kwargs: dict[str, Any] = {
        "model": profile.model,
        "messages": messages,
        "api_key": profile.api_key,
        "max_tokens": profile.max_output_tokens,
        "temperature": profile.temperature,
        "timeout": profile.timeout_seconds,
    }
    if profile.api_base:
        kwargs["api_base"] = profile.api_base
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if response_format:
        kwargs["response_format"] = response_format
    started = time.perf_counter()
    response = await acompletion(**kwargs)
    latency_ms = round((time.perf_counter() - started) * 1000)
    message = response.choices[0].message
    calls = []
    for call in message.tool_calls or []:
        calls.append(
            {
                "id": call.id,
                "name": call.function.name,
                "arguments": json.loads(call.function.arguments or "{}"),
            }
        )
    usage = getattr(response, "usage", None)
    try:
        cost = float(completion_cost(completion_response=response))
    except Exception:
        cost = None
    return LLMResult(
        content=message.content or "",
        tool_calls=calls,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        estimated_cost=cost,
        latency_ms=latency_ms,
    )
