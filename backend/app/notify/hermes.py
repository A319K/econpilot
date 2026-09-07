import asyncio
import logging
import shutil

from app.config import get_settings
from app.notify.base import Notifier

logger = logging.getLogger(__name__)

_warned_missing_binary = False


class HermesNotifier(Notifier):
    name = "hermes"

    def __init__(self) -> None:
        settings = get_settings()
        self._target = settings.hermes_send_target
        self._bin = settings.hermes_bin

    async def send(self, subject: str, body: str) -> bool:
        global _warned_missing_binary

        if shutil.which(self._bin) is None:
            if not _warned_missing_binary:
                logger.error("hermes binary %r not found on PATH; notifications disabled", self._bin)
                _warned_missing_binary = True
            return False

        message = f"{subject}\n\n{body}" if body else subject

        try:
            proc = await asyncio.create_subprocess_exec(
                self._bin,
                "send",
                self._target,
                "-m",
                message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
        except OSError as exc:
            logger.error("hermes send failed to start: %s", exc)
            return False

        if proc.returncode != 0:
            logger.error("hermes send exited %s: %s", proc.returncode, stderr.decode(errors="replace"))
            return False

        return True
