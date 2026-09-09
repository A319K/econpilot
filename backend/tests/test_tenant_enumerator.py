import json
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from app.discovery.ats_probe import ProbeIncompleteError
from app.discovery.tenant_enumerator import (
    EmployerName,
    enumerate_tenants,
    load_employer_names,
    write_candidates,
)
from app.models.company import AtsType


def test_load_employer_names_deduplicates_and_preserves_sources(tmp_path):
    source = tmp_path / "employers.csv"
    source.write_text(
        "Company Name,source\nThe Brattle Group,Econ consulting directory\n"
        " the brattle group ,Asset managers\nPoint72,Asset managers\n",
        encoding="utf-8",
    )

    records = load_employer_names(source)

    assert records == [
        EmployerName("The Brattle Group", ("Econ consulting directory", "Asset managers")),
        EmployerName("Point72", ("Asset managers",)),
    ]


@pytest.mark.asyncio
async def test_enumeration_caches_hits_and_misses_without_ingesting(tmp_path):
    cache_path = tmp_path / "cache.json"
    employers = [EmployerName("Acme", ("Directory",)), EmployerName("No Board")]
    calls: list[str] = []

    async def probe(_client, name):
        calls.append(name)
        return (AtsType.greenhouse, "acme") if name == "Acme" else None

    now = datetime(2026, 9, 9, tzinfo=timezone.utc)
    candidates = await enumerate_tenants(
        employers,
        cache_path,
        request_interval_seconds=0,
        probe=probe,
        now=now,
    )

    assert calls == ["Acme", "No Board"]
    assert candidates == [
        {
            "name": "Acme",
            "ats_type": "greenhouse",
            "ats_board_id": "acme",
            "sources": ["Directory"],
            "probed_at": now.isoformat(),
            "is_target": False,
        }
    ]
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["entries"]["no board"]["status"] == "miss"

    calls.clear()
    cached_candidates = await enumerate_tenants(
        employers,
        cache_path,
        request_interval_seconds=0,
        probe=probe,
        now=now + timedelta(days=30),
    )
    assert calls == []
    assert cached_candidates == candidates


@pytest.mark.asyncio
async def test_incomplete_probe_is_not_negative_cached(tmp_path):
    cache_path = tmp_path / "cache.json"
    progress: list[str] = []

    async def probe(_client, _name):
        raise ProbeIncompleteError("rate limited")

    candidates = await enumerate_tenants(
        [EmployerName("Retry Corp")],
        cache_path,
        request_interval_seconds=0,
        probe=probe,
        progress=lambda _i, _n, _name, message: progress.append(message),
    )

    assert candidates == []
    assert not cache_path.exists()
    assert progress[-1] == "temporarily unavailable; will retry"


@pytest.mark.asyncio
async def test_stale_cache_entry_is_probed_again(tmp_path):
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    "acme": {
                        "name": "Acme",
                        "sources": [],
                        "status": "miss",
                        "probed_at": old.isoformat(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    async def probe(_client, _name):
        return AtsType.ashby, "acme"

    candidates = await enumerate_tenants(
        [EmployerName("Acme")],
        cache_path,
        request_interval_seconds=0,
        probe=probe,
        now=old + timedelta(days=91),
    )

    assert candidates[0]["ats_type"] == "ashby"


def test_write_candidates_uses_review_only_top_level_key(tmp_path):
    output = tmp_path / "candidates.yaml"
    write_candidates(output, [{"name": "Acme", "is_target": False}])

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert "companies" not in payload
    assert payload["candidates"] == [{"name": "Acme", "is_target": False}]
