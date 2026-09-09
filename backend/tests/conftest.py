import os
import shutil
import tempfile

import pytest

os.environ.setdefault("LLM_API_KEY", "test-key")

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_db.name}")

# Isolate the suite from a developer's local backend/.env. Environment
# variables take precedence over the .env file in pydantic-settings, so
# forcing these here guarantees the notifier/watcher defaults tests assert on
# regardless of what a contributor has set locally (e.g. NOTIFIER=telegram).
# Tests that need other values monkeypatch them and clear get_settings' cache.
os.environ["NOTIFIER"] = "none"
os.environ["WATCHER_ENABLED"] = "false"
os.environ["USAJOBS_API_KEY"] = ""
os.environ["USAJOBS_USER_AGENT"] = ""

from app.db import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401

Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    from app.llm import client as llm_client

    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(llm_client.asyncio, "sleep", instant_sleep)


@pytest.fixture(autouse=True)
def _use_example_profile(monkeypatch):
    """Pin the suite to profile.example.yaml so a developer's real profile.yaml
    (name, EEO answers, etc.) can't change what the tests assert on. Mirrors the
    .env isolation above. Tests that need a different profile monkeypatch
    get_profile directly."""
    from app import profile as profile_mod

    monkeypatch.setattr(profile_mod, "PROFILE_PATH", profile_mod.PROFILE_EXAMPLE_PATH)
    profile_mod.get_profile.cache_clear()
    yield
    profile_mod.get_profile.cache_clear()


def pytest_collection_modifyitems(config, items):
    import importlib.util

    from app.config import get_settings

    latex_available = bool(shutil.which(get_settings().latex_compiler))
    playwright_available = importlib.util.find_spec("playwright") is not None

    skip_latex = pytest.mark.skip(reason="LaTeX compiler not installed")
    skip_agent = pytest.mark.skip(reason="Playwright not installed (install the 'agent' extra)")
    for item in items:
        if "latex" in item.keywords and not latex_available:
            item.add_marker(skip_latex)
        if "agent" in item.keywords and not playwright_available:
            item.add_marker(skip_agent)
