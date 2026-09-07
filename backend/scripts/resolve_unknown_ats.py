"""Actively resolve unknown-ATS companies against the job-board APIs.

Companies we know by name but not by ATS are silently skipped by every scan.
This probes their name against Greenhouse/Lever/Ashby and persists any hit, so
they become directly scannable. Safe to re-run; each company is probed at most
once per the configured reprobe window.

Usage (run from backend/):
    .venv/bin/python scripts/resolve_unknown_ats.py [--limit N] [--reprobe-days D]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.discovery.ats_probe import resolve_unknown_companies  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="cap companies probed")
    parser.add_argument("--reprobe-days", type=int, default=30, help="skip companies probed within N days")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = await resolve_unknown_companies(
            db, reprobe_after_days=args.reprobe_days, limit=args.limit
        )
    finally:
        db.close()

    print(f"probed:   {summary['probed']}")
    print(f"resolved: {summary['resolved']}")
    for line in summary["resolved_names"]:
        print(f"  + {line}")


if __name__ == "__main__":
    asyncio.run(main())
