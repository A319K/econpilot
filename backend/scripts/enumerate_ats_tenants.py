"""Find Greenhouse, Lever, and Ashby boards from a broad employer list.

This command does not add companies to EconPilot or scan any jobs. It writes a
review-only candidate file so the user can decide which employers belong in
their roster.

Usage (run from backend/):
    .venv/bin/python scripts/enumerate_ats_tenants.py employers.csv
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.discovery.tenant_enumerator import (  # noqa: E402
    DEFAULT_CONCURRENCY,
    DEFAULT_REPROBE_AFTER_DAYS,
    DEFAULT_REQUEST_INTERVAL_SECONDS,
    enumerate_tenants,
    load_employer_names,
    write_candidates,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE = REPO_ROOT / ".ats_probe_cache.json"
DEFAULT_OUTPUT = REPO_ROOT / "ats_candidates.yaml"


def _progress(index: int, total: int, name: str, message: str) -> None:
    print(f"[{index}/{total}] {name}: {message}", flush=True)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find public job boards and write suggestions for review."
    )
    parser.add_argument("employer_file", type=Path, help="CSV, JSON, YAML, or text employer list")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--reprobe-days", type=int, default=DEFAULT_REPROBE_AFTER_DAYS)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--request-interval",
        type=float,
        default=DEFAULT_REQUEST_INTERVAL_SECONDS,
        help="minimum seconds between all outgoing board requests",
    )
    args = parser.parse_args()

    try:
        employers = load_employer_names(args.employer_file)
        print(
            f"Checking {len(employers)} employers. Results are suggestions only; "
            "no jobs or companies will be added.",
            flush=True,
        )
        candidates = await enumerate_tenants(
            employers,
            args.cache,
            reprobe_after_days=args.reprobe_days,
            concurrency=args.concurrency,
            request_interval_seconds=args.request_interval,
            progress=_progress,
        )
        write_candidates(args.output, candidates)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Could not enumerate employers: {exc}\n")

    print(f"Done. Found {len(candidates)} candidate boards.", flush=True)
    print(f"Review them at: {args.output}", flush=True)
    print("Nothing was added to your EconPilot roster.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
