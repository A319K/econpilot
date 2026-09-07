import asyncio
import json
import re

import httpx

from app.config import get_settings

TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(Exception):
    pass


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


async def _request(
    client: httpx.AsyncClient, payload: dict, api_key: str
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                raise LLMError(f"LLM request failed: {exc}") from exc
            await asyncio.sleep(2**attempt)
            continue

        if response.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
            await asyncio.sleep(2**attempt)
            continue

        if response.status_code >= 400:
            raise LLMError(
                f"LLM request failed with status {response.status_code}: {response.text}"
            )

        return response

    raise LLMError(f"LLM request failed after retries: {last_exc}")


async def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    settings = get_settings()
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(
        base_url=settings.llm_base_url, timeout=TIMEOUT_SECONDS
    ) as client:
        response = await _request(client, payload, settings.llm_api_key)

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason")
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {data}") from exc

    if content is None:
        # Reasoning models (e.g. glm-5.2) can spend the entire max_tokens
        # budget on hidden reasoning tokens and emit no visible content,
        # especially with finish_reason "length" (truncated before the
        # model reached its answer). Fail loudly instead of returning None
        # from a function typed to return str.
        raise LLMError(
            f"LLM returned no content (finish_reason={finish_reason!r}); "
            "the model likely ran out of max_tokens during reasoning before "
            "producing a visible answer - try increasing max_tokens"
        )

    return content


async def complete_json(system: str, user: str, schema_hint: str, max_tokens: int = 1024) -> dict:
    json_system = (
        f"{system}\n\n"
        "Respond with ONLY valid JSON, no prose, no markdown code fences. "
        f"The JSON must conform to this shape: {schema_hint}"
    )

    raw = await complete(json_system, user, max_tokens=max_tokens)
    cleaned = _strip_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    corrective_user = (
        f"Your previous response could not be parsed as JSON. It was:\n{raw}\n\n"
        f"Return ONLY valid JSON matching this shape: {schema_hint}"
    )
    retry_raw = await complete(json_system, corrective_user, max_tokens=max_tokens)
    retry_cleaned = _strip_fences(retry_raw)

    try:
        return json.loads(retry_cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Failed to parse LLM response as JSON after retry: {retry_raw}") from exc
