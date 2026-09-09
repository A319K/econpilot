import httpx
import pytest

from app.discovery.ats_probe import ProbeIncompleteError, _hit
from app.models.company import AtsType


@pytest.mark.asyncio
async def test_hit_treats_clean_404s_as_a_cacheable_miss():
    async def handler(request):
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await _hit(client, "missing") is None


@pytest.mark.asyncio
async def test_hit_accepts_a_valid_board_with_no_current_openings():
    async def handler(request):
        if "greenhouse" in request.url.host:
            return httpx.Response(200, json={"jobs": []}, request=request)
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await _hit(client, "quiet-board") == (AtsType.greenhouse, "quiet-board")


@pytest.mark.asyncio
async def test_hit_does_not_turn_rate_limit_into_negative_result():
    async def handler(request):
        status = 429 if "greenhouse" in request.url.host else 404
        return httpx.Response(status, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProbeIncompleteError, match="Greenhouse returned HTTP 429"):
            await _hit(client, "retry")
