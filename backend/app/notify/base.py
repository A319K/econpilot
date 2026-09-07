from abc import ABC, abstractmethod

from pydantic import BaseModel


class Notification(BaseModel):
    """Plain subject/body pair. Adapters decide how to format/escape this
    for their transport (e.g. Telegram MarkdownV2)."""

    subject: str
    body: str

    def as_text(self) -> str:
        return f"{self.subject}\n\n{self.body}" if self.body else self.subject


class Notifier(ABC):
    name: str

    @abstractmethod
    async def send(self, subject: str, body: str) -> bool:
        raise NotImplementedError
