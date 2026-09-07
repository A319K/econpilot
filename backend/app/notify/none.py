import logging

from app.notify.base import Notifier

logger = logging.getLogger(__name__)


class NoneNotifier(Notifier):
    name = "none"

    async def send(self, subject: str, body: str) -> bool:
        logger.debug("notifier disabled, dropping notification: %s", subject)
        return True
