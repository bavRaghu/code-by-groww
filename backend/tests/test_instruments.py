import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_all_instruments(client: AsyncClient):
    response = await client.get("/api/v1/instruments")
    assert response.status_code == 200
    instruments = response.json()
    assert len(instruments) >= 6
    symbols = [inst["nse_symbol"] for inst in instruments]
    for s in ["TCS", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "ICICIBANK"]:
        assert s in symbols


@pytest.mark.asyncio
async def test_search_by_symbol(client: AsyncClient):
    # Case insensitive search by symbol
    response = await client.get("/api/v1/instruments?search=tcs")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any(inst["nse_symbol"] == "TCS" for inst in results)


@pytest.mark.asyncio
async def test_search_by_company_name(client: AsyncClient):
    # Search by partial company name
    response = await client.get("/api/v1/instruments?search=reliance")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any("Reliance" in inst["company_name"] for inst in results)


@pytest.mark.asyncio
async def test_search_no_match(client: AsyncClient):
    response = await client.get("/api/v1/instruments?search=NONEXISTENT_XYZ_123")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_limit_and_bounds(client: AsyncClient):
    # Test valid limit
    res_limit_2 = await client.get("/api/v1/instruments?limit=2")
    assert res_limit_2.status_code == 200
    assert len(res_limit_2.json()) == 2

    # Test limit below lower bound (ge=1) -> 422
    res_zero = await client.get("/api/v1/instruments?limit=0")
    assert res_zero.status_code == 422

    # Test limit above upper bound (le=100) -> 422
    res_high = await client.get("/api/v1/instruments?limit=101")
    assert res_high.status_code == 422

    # Test default limit returns at most 50
    res_default = await client.get("/api/v1/instruments")
    assert res_default.status_code == 200
    assert len(res_default.json()) <= 50
