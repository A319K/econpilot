from app.config import get_settings
from app.notify.base import Notifier
from app.notify.hermes import HermesNotifier
from app.notify.none import NoneNotifier
from app.notify.telegram import TelegramNotifier

_NOTIFIER_MAP: dict[str, type[Notifier]] = {
    "none": NoneNotifier,
    "telegram": TelegramNotifier,
    "hermes": HermesNotifier,
}


def get_notifier() -> Notifier:
    settings = get_settings()
    cls = _NOTIFIER_MAP.get(settings.notifier, NoneNotifier)
    return cls()
