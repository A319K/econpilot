import httpx
import pytest

from app.config import get_settings
from app.notify.factory import get_notifier
from app.notify.hermes import HermesNotifier
from app.notify.none import NoneNotifier
from app.notify.telegram import TelegramNotifier, escape_markdown_v2


def test_escape_markdown_v2_escapes_special_chars():
    assert escape_markdown_v2("C++ Engineer (Senior)!") == "C\\+\\+ Engineer \\(Senior\\)\\!"


@pytest.mark.asyncio
async def test_telegram_notifier_sends_successfully(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    captured = {}

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, timeout=10.0):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    notifier = TelegramNotifier()
    ok = await notifier.send("New job!", "Acme | SWE Intern")

    assert ok is True
    assert captured["json"]["chat_id"] == "12345"
    assert captured["json"]["parse_mode"] == "MarkdownV2"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_telegram_notifier_missing_credentials_returns_false(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")

    notifier = TelegramNotifier()
    ok = await notifier.send("subject", "body")

    assert ok is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_telegram_notifier_swallows_http_errors(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    class FakeClient:
        def __init__(self, timeout=10.0):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    notifier = TelegramNotifier()
    ok = await notifier.send("subject", "body")

    assert ok is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_hermes_notifier_missing_binary_returns_false_and_never_raises(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("HERMES_BIN", "definitely-not-a-real-binary-xyz")

    notifier = HermesNotifier()
    ok = await notifier.send("subject", "body")

    assert ok is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_hermes_notifier_invokes_fake_binary_on_path(monkeypatch, tmp_path):
    get_settings.cache_clear()
    fake_bin = tmp_path / "hermes"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    monkeypatch.setenv("PATH", f"{tmp_path}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("HERMES_BIN", "hermes")
    monkeypatch.setenv("HERMES_SEND_TARGET", "telegram")

    notifier = HermesNotifier()
    ok = await notifier.send("Job title with 'quotes' and $pecial chars", "body")

    assert ok is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_hermes_notifier_nonzero_exit_returns_false(monkeypatch, tmp_path):
    get_settings.cache_clear()
    fake_bin = tmp_path / "hermes"
    fake_bin.write_text("#!/bin/sh\nexit 1\n")
    fake_bin.chmod(0o755)

    monkeypatch.setenv("PATH", f"{tmp_path}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("HERMES_BIN", "hermes")

    notifier = HermesNotifier()
    ok = await notifier.send("subject", "body")

    assert ok is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_none_notifier_always_succeeds():
    notifier = NoneNotifier()
    assert await notifier.send("subject", "body") is True


def test_factory_selects_notifier_by_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("NOTIFIER", "telegram")
    assert isinstance(get_notifier(), TelegramNotifier)
    get_settings.cache_clear()

    monkeypatch.setenv("NOTIFIER", "hermes")
    assert isinstance(get_notifier(), HermesNotifier)
    get_settings.cache_clear()

    monkeypatch.setenv("NOTIFIER", "none")
    assert isinstance(get_notifier(), NoneNotifier)
    get_settings.cache_clear()


def test_factory_defaults_to_none_for_unknown_value(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("NOTIFIER", "carrier-pigeon")
    assert isinstance(get_notifier(), NoneNotifier)
    get_settings.cache_clear()
