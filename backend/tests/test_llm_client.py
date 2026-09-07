import httpx
import pytest

from app.llm import client as llm_client
from app.llm.client import LLMError, complete, complete_json


_RealAsyncClient = httpx.AsyncClient


def _install_transport(monkeypatch, handler):
    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", fake_async_client)


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.mark.asyncio
async def test_complete_returns_content(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("hello world")

    _install_transport(monkeypatch, handler)

    result = await complete("system prompt", "user prompt")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_complete_raises_llm_error_when_content_is_null(monkeypatch):
    # Reasoning models (e.g. glm-5.2) can burn the whole max_tokens budget
    # on hidden reasoning and return content=null with finish_reason
    # "length" instead of a visible answer.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "length", "message": {"role": "assistant", "content": None}}
                ]
            },
        )

    _install_transport(monkeypatch, handler)

    with pytest.raises(LLMError, match="no content"):
        await complete("system prompt", "user prompt")


@pytest.mark.asyncio
async def test_complete_json_parses_plain_json(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response('{"answer": 42}')

    _install_transport(monkeypatch, handler)

    result = await complete_json("system", "user", schema_hint='{"answer": int}')
    assert result == {"answer": 42}


@pytest.mark.asyncio
async def test_complete_json_strips_code_fences(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response('```json\n{"answer": 7}\n```')

    _install_transport(monkeypatch, handler)

    result = await complete_json("system", "user", schema_hint='{"answer": int}')
    assert result == {"answer": 7}


@pytest.mark.asyncio
async def test_complete_json_retries_once_on_parse_failure(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return _chat_response("not json at all")
        return _chat_response('{"answer": 1}')

    _install_transport(monkeypatch, handler)

    result = await complete_json("system", "user", schema_hint='{"answer": int}')
    assert result == {"answer": 1}
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_complete_json_raises_llm_error_after_retry_fails(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("still not json")

    _install_transport(monkeypatch, handler)

    with pytest.raises(LLMError):
        await complete_json("system", "user", schema_hint='{"answer": int}')


@pytest.mark.asyncio
async def test_complete_retries_on_5xx_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, text="server error")
        return _chat_response("recovered")

    _install_transport(monkeypatch, handler)

    result = await complete("system", "user")
    assert result == "recovered"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_complete_raises_llm_error_on_persistent_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    _install_transport(monkeypatch, handler)

    with pytest.raises(LLMError):
        await complete("system", "user")


@pytest.mark.asyncio
async def test_complete_raises_llm_error_on_4xx(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    _install_transport(monkeypatch, handler)

    with pytest.raises(LLMError):
        await complete("system", "user")
