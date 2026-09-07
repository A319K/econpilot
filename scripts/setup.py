#!/usr/bin/env python3
"""EconPilot first-run setup.

Copies the example configs into place (prompting where a value is needed), runs
the database migrations, and optionally seeds example companies. Safe to re-run:
existing files are never overwritten without asking.

    python scripts/setup.py

Works non-interactively too (e.g. in a script or CI): with no TTY it takes the
safe default for every prompt (never overwrites, skips optional steps).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

ENV_EXAMPLE = REPO_ROOT / ".env.example"
ENV_TARGET = BACKEND / ".env"
PROFILE_EXAMPLE = REPO_ROOT / "profile.example.yaml"
PROFILE_TARGET = REPO_ROOT / "profile.yaml"
COMPANIES_EXAMPLE = REPO_ROOT / "companies.example.yaml"
COMPANIES_TARGET = REPO_ROOT / "companies.yaml"

INTERACTIVE = sys.stdin.isatty() and sys.stdout.isatty()


# --- small prompt helpers -------------------------------------------------

def ask(prompt: str, default: str = "") -> str:
    """Prompt for a line of input; return `default` when non-interactive."""
    if not INTERACTIVE:
        return default
    try:
        reply = input(prompt).strip()
    except EOFError:
        return default
    return reply or default


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    reply = ask(prompt + suffix, "y" if default else "n").lower()
    return reply in {"y", "yes"}


def note(msg: str) -> None:
    print(f"  {msg}")


# --- .env -----------------------------------------------------------------

def set_env_value(text: str, key: str, value: str) -> str:
    """Set KEY=value in dotenv text: replace an existing (possibly commented)
    line, otherwise append. Leaves the rest of the file untouched."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").rstrip()
        if stripped.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            return "\n".join(lines) + "\n"
    lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def setup_env() -> None:
    print("\n[1/5] Backend environment (backend/.env)")
    if ENV_TARGET.exists():
        if not ask_yes_no(f"  {ENV_TARGET.relative_to(REPO_ROOT)} exists. Overwrite?", False):
            note("keeping existing backend/.env")
            return

    text = ENV_EXAMPLE.read_text()

    key = ask("  OpenRouter/LLM API key (blank to fill in later): ", "")
    if key:
        text = set_env_value(text, "LLM_API_KEY", key)

    notifier = ask("  Notifier for the watcher [none/telegram/hermes] (default none): ", "none").lower()
    if notifier not in {"none", "telegram", "hermes"}:
        notifier = "none"
    text = set_env_value(text, "NOTIFIER", notifier)

    if notifier == "telegram":
        token = ask("  Telegram bot token: ", "")
        chat_id = ask("  Telegram chat id: ", "")
        if token:
            text = set_env_value(text, "TELEGRAM_BOT_TOKEN", token)
        if chat_id:
            text = set_env_value(text, "TELEGRAM_CHAT_ID", chat_id)

    ENV_TARGET.write_text(text)
    note(f"wrote {ENV_TARGET.relative_to(REPO_ROOT)}  (notifier={notifier}, key={'set' if key else 'empty'})")


# --- profile / companies --------------------------------------------------

def copy_if_absent(src: Path, dst: Path, label: str, *, ask_overwrite: bool = True) -> None:
    rel = dst.relative_to(REPO_ROOT)
    if dst.exists():
        if ask_overwrite and ask_yes_no(f"  {rel} exists. Overwrite with the example?", False):
            shutil.copyfile(src, dst)
            note(f"overwrote {rel}")
        else:
            note(f"keeping existing {rel}")
        return
    shutil.copyfile(src, dst)
    note(f"created {rel}  ({label})")


def setup_profile() -> None:
    print("\n[2/5] Personal profile (profile.yaml)")
    copy_if_absent(PROFILE_EXAMPLE, PROFILE_TARGET, "edit this with your real details")


def setup_companies() -> None:
    print("\n[3/5] Target companies (companies.yaml)")
    if COMPANIES_TARGET.exists():
        note(f"keeping existing {COMPANIES_TARGET.relative_to(REPO_ROOT)}")
        return
    if ask_yes_no("  Create companies.yaml from the example list?", True):
        copy_if_absent(COMPANIES_EXAMPLE, COMPANIES_TARGET, "your target-company list", ask_overwrite=False)
    else:
        note("skipped; add companies later under Settings or edit companies.yaml")


# --- migrations + seeding -------------------------------------------------

def backend_python() -> str:
    venv_py = BACKEND / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.exists() else sys.executable


def run_migrations() -> None:
    print("\n[4/5] Database migrations (alembic upgrade head)")
    py = backend_python()
    try:
        subprocess.run([py, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)
        note("database is up to date")
    except FileNotFoundError:
        note(f"could not run {py}; install backend deps first (see README), then re-run")
    except subprocess.CalledProcessError:
        note("alembic failed. Install backend deps: cd backend && uv pip install -e '.[dev]'")


def seed_companies() -> None:
    print("\n[5/5] Seed companies into the database")
    if not COMPANIES_TARGET.exists() and not COMPANIES_EXAMPLE.exists():
        note("no companies file to seed; skipping")
        return
    if not ask_yes_no("  Seed companies now?", True):
        note("skipped; run `python scripts/seed_companies.py` from backend/ anytime")
        return
    py = backend_python()
    try:
        subprocess.run([py, "scripts/seed_companies.py"], cwd=BACKEND, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        note("seeding failed (install backend deps and run migrations first)")


def print_next_steps() -> None:
    print(
        "\nSetup complete. Next:\n"
        "  1. Fill in LLM_API_KEY in backend/.env if you skipped it.\n"
        "  2. Edit profile.yaml with your real details.\n"
        "  3. Start the backend:  cd backend && .venv/bin/uvicorn app.main:app --reload\n"
        "  4. Start the frontend: cd frontend && npm install && npm run dev\n"
        "  5. Open http://localhost:5173 , then hit SCAN on the queue.\n"
        "\nSee the README for the full quickstart and the Docker option."
    )


def main() -> None:
    print("EconPilot setup")
    if not INTERACTIVE:
        print("(non-interactive: taking safe defaults, not overwriting anything)")
    setup_env()
    setup_profile()
    setup_companies()
    run_migrations()
    seed_companies()
    print_next_steps()


if __name__ == "__main__":
    main()
