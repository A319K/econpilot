"""Discover public ATS boards from an employer-name list without ingesting jobs.

Enumeration deliberately writes a review artifact rather than ``Company`` rows.
That keeps newly discovered employers out of ordinary scans until a user chooses
to add them to their roster.
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from typing import Any

import httpx
import yaml

from app.discovery.ats_probe import ProbeIncompleteError, probe_company_ats
from app.models.company import AtsType

CACHE_VERSION = 1
DEFAULT_REPROBE_AFTER_DAYS = 90
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.35
DEFAULT_CONCURRENCY = 3
_USER_AGENT = "EconPilot/0.1 tenant-enumerator (local user-initiated discovery)"

ProgressCallback = Callable[[int, int, str, str], None]
ProbeFunction = Callable[[Any, str], Awaitable[tuple[AtsType, str] | None]]


@dataclass(frozen=True)
class EmployerName:
    name: str
    sources: tuple[str, ...] = ()


def _normalized_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().casefold()


def _record(name: Any, source: Any = None) -> EmployerName | None:
    cleaned_name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not cleaned_name:
        return None
    cleaned_source = re.sub(r"\s+", " ", str(source or "")).strip()
    return EmployerName(cleaned_name, (cleaned_source,) if cleaned_source else ())


def _records_from_rows(rows: list[Any], default_source: str = "") -> list[EmployerName]:
    records: list[EmployerName] = []
    for row in rows:
        if isinstance(row, str):
            item = _record(row, default_source)
        elif isinstance(row, dict):
            normalized = {
                re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_"): value
                for key, value in row.items()
            }
            item = _record(
                normalized.get("name")
                or normalized.get("company")
                or normalized.get("company_name")
                or normalized.get("employer")
                or normalized.get("employer_name")
                or normalized.get("organization")
                or normalized.get("organization_name"),
                normalized.get("source") or normalized.get("list") or default_source,
            )
        else:
            item = None
        if item is not None:
            records.append(item)
    return records


def _deduplicate(records: list[EmployerName]) -> list[EmployerName]:
    by_name: dict[str, tuple[str, list[str]]] = {}
    for record in records:
        key = _normalized_name(record.name)
        if key not in by_name:
            by_name[key] = (record.name, [])
        sources = by_name[key][1]
        for source in record.sources:
            if source and source not in sources:
                sources.append(source)
    return [EmployerName(name, tuple(sources)) for name, sources in by_name.values()]


def load_employer_names(path: Path) -> list[EmployerName]:
    """Load names from CSV, JSON, YAML, or one-name-per-line text files."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        records = _records_from_rows(rows, path.name)
    elif suffix in {".json", ".yaml", ".yml"}:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle) if suffix == ".json" else yaml.safe_load(handle)
        if isinstance(data, dict):
            rows = (
                data.get("employers")
                or data.get("companies")
                or data.get("organizations")
                or []
            )
            default_source = str(data.get("source") or path.name)
        elif isinstance(data, list):
            rows, default_source = data, path.name
        else:
            raise ValueError(
                "Employer file must contain a list or an object with an employers list."
            )
        records = _records_from_rows(rows, default_source)
    else:
        records = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, source = line.partition("\t")
            item = _record(name, source or path.name)
            if item is not None:
                records.append(item)

    records = _deduplicate(records)
    if not records:
        raise ValueError(
            "No employer names were found. Use a name/company/employer column "
            "or one name per line."
        )
    return records


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not read the probe cache at {path}: {exc}") from exc
    if payload.get("version") != CACHE_VERSION or not isinstance(payload.get("entries"), dict):
        raise ValueError(f"The probe cache at {path} has an unsupported format.")
    return payload["entries"]


def _write_cache(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"version": CACHE_VERSION, "entries": entries}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _cached_entry(
    entries: dict[str, dict[str, Any]], record: EmployerName, stale_before: datetime
) -> dict[str, Any] | None:
    entry = entries.get(_normalized_name(record.name))
    if entry is None:
        return None
    try:
        probed_at = datetime.fromisoformat(str(entry["probed_at"]))
    except (KeyError, TypeError, ValueError):
        return None
    if entry.get("status") not in {"miss", "resolved"}:
        return None
    if entry["status"] == "resolved" and not all(
        entry.get(field) for field in ("ats_type", "ats_board_id")
    ):
        return None
    if probed_at.tzinfo is None:
        probed_at = probed_at.replace(tzinfo=timezone.utc)
    return entry if probed_at >= stale_before else None


class _RequestPacer:
    def __init__(self, minimum_interval: float):
        self.minimum_interval = minimum_interval
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._next_request_at - monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request_at = monotonic() + self.minimum_interval


class _PacedClient:
    def __init__(self, client: httpx.AsyncClient, pacer: _RequestPacer):
        self._client = client
        self._pacer = pacer

    async def get(self, *args, **kwargs):
        await self._pacer.wait()
        return await self._client.get(*args, **kwargs)


async def enumerate_tenants(
    employers: list[EmployerName],
    cache_path: Path,
    *,
    reprobe_after_days: int = DEFAULT_REPROBE_AFTER_DAYS,
    concurrency: int = DEFAULT_CONCURRENCY,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    progress: ProgressCallback | None = None,
    probe: ProbeFunction = probe_company_ats,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return resolved review candidates, reusing a durable hit/miss cache."""
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    if request_interval_seconds < 0:
        raise ValueError("request_interval_seconds cannot be negative")
    if reprobe_after_days < 0:
        raise ValueError("reprobe_after_days cannot be negative")

    employers = _deduplicate(employers)
    entries = _load_cache(cache_path)
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(days=reprobe_after_days)
    semaphore = asyncio.Semaphore(concurrency)
    pacer = _RequestPacer(request_interval_seconds)
    total = len(employers)

    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": _USER_AGENT}) as raw_client:
        client = _PacedClient(raw_client, pacer)

        async def worker(index: int, employer: EmployerName) -> None:
            cached = _cached_entry(entries, employer, stale_before)
            if cached is not None:
                if progress:
                    progress(index, total, employer.name, f"cached {cached['status']}")
                return

            try:
                async with semaphore:
                    if progress:
                        progress(index, total, employer.name, "checking public job boards")
                    found = await probe(client, employer.name)
            except ProbeIncompleteError:
                if progress:
                    progress(index, total, employer.name, "temporarily unavailable; will retry")
                return

            entry: dict[str, Any] = {
                "name": employer.name,
                "sources": list(employer.sources),
                "status": "resolved" if found else "miss",
                "probed_at": now.isoformat(),
            }
            if found:
                entry["ats_type"] = found[0].value
                entry["ats_board_id"] = found[1]
            entries[_normalized_name(employer.name)] = entry
            _write_cache(cache_path, entries)
            if progress:
                label = (
                    f"found {found[0].value}/{found[1]}"
                    if found
                    else "no supported board found"
                )
                progress(index, total, employer.name, label)

        await asyncio.gather(
            *(worker(index, employer) for index, employer in enumerate(employers, 1))
        )

    candidates = []
    for employer in employers:
        entry = entries.get(_normalized_name(employer.name), {})
        if entry.get("status") != "resolved":
            continue
        candidates.append(
            {
                "name": employer.name,
                "ats_type": entry["ats_type"],
                "ats_board_id": entry["ats_board_id"],
                "sources": list(employer.sources or tuple(entry.get("sources", []))),
                "probed_at": entry["probed_at"],
                "is_target": False,
            }
        )
    return candidates


def write_candidates(path: Path, candidates: list[dict[str, Any]]) -> None:
    """Atomically write a review-only artifact that seed_companies cannot ingest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(
            {
                "notice": (
                    "Review these suggestions in EconPilot before adding them to your roster."
                ),
                "candidates": candidates,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
