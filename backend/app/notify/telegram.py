import logging
import re

import httpx

from app.config import get_settings
from app.notify.base import Notifier

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"

# Characters MarkdownV2 requires escaping outside of explicit formatting
# entities. See https://core.telegram.org/bots/api#markdownv2-style
_MARKDOWNV2_SPECIAL_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_markdown_v2(text: str) -> str:
    return _MARKDOWNV2_SPECIAL_RE.sub(r"\\\1", text)


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self) -> None:
        settings = get_settings()
        self._bot_token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id

    async def send(self, subject: str, body: str) -> bool:
        if not self._bot_token or not self._chat_id:
            logger.error("telegram notifier missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
            return False

        text = f"{subject}\n\n{body}" if body else subject
        url = f"{_TELEGRAM_API_BASE}/bot{self._bot_token}/sendMessage"

        payload = {
            "chat_id": self._chat_id,
            "text": escape_markdown_v2(text),
            "parse_mode": "MarkdownV2",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.error("telegram send failed: %s", exc)
            return False

        if response.status_code == 200:
            return True

        # MarkdownV2 escaping can still be rejected by Telegram for edge cases
        # (e.g. malformed entity pairs) - fall back to plain text once.
        logger.error("telegram send failed (%s), retrying as plain text", response.status_code)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                fallback = await client.post(
                    url, json={"chat_id": self._chat_id, "text": text}
                )
        except httpx.HTTPError as exc:
            logger.error("telegram plain-text fallback failed: %s", exc)
            return False

        return fallback.status_code == 200
