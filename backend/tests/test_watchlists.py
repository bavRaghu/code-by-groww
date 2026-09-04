import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_watchlist_crud_lifecycle(client: AsyncClient):
    # 1. Create watchlist
    create_res = await client.post("/api/v1/watchlists", json={"name": "Tech & Banking"})
    assert create_res.status_code == 201
    wl = create_res.json()
    assert wl["name"] == "Tech & Banking"
    wl_id = wl["id"]

    # 2. List watchlists
    list_res = await client.get("/api/v1/watchlists")
    assert list_res.status_code == 200
    wls = list_res.json()
    assert any(w["id"] == wl_id for w in wls)

    # 3. Retrieve watchlist by ID
    get_res = await client.get(f"/api/v1/watchlists/{wl_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == wl_id

    # 4. Rename watchlist
    rename_res = await client.patch(f"/api/v1/watchlists/{wl_id}", json={"name": "Core Holdings"})
    assert rename_res.status_code == 200
    assert rename_res.json()["name"] == "Core Holdings"

    # 5. Delete watchlist
    del_res = await client.delete(f"/api/v1/watchlists/{wl_id}")
    assert del_res.status_code == 204

    # 6. Verify deleted
    get_del = await client.get(f"/api/v1/watchlists/{wl_id}")
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_items_management(client: AsyncClient):
    # Setup: get instruments
    inst_res = await client.get("/api/v1/instruments")
    instruments = inst_res.json()
    inst_map = {inst["nse_symbol"]: inst["id"] for inst in instruments}

    tcs_id = inst_map["TCS"]
    infy_id = inst_map["INFY"]
    rel_id = inst_map["RELIANCE"]

    # Create watchlist
    create_wl = await client.post("/api/v1/watchlists", json={"name": "Membership Test"})
    wl_id = create_wl.json()["id"]

    # Add TCS
    add_tcs = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": tcs_id})
    assert add_tcs.status_code == 201
    assert add_tcs.json()["instrument_id"] == tcs_id
    assert add_tcs.json()["position"] == 0

    # Add INFY
    add_infy = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": infy_id})
    assert add_infy.status_code == 201
    assert add_infy.json()["instrument_id"] == infy_id
    assert add_infy.json()["position"] == 1

    # Attempt adding TCS again (duplicate -> 409 Conflict)
    dup_res = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": tcs_id})
    assert dup_res.status_code == 409

    # Add RELIANCE
    add_rel = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": rel_id})
    assert add_rel.status_code == 201
    assert add_rel.json()["position"] == 2

    # Verify 3 items retrieved
    get_wl = await client.get(f"/api/v1/watchlists/{wl_id}")
    items = get_wl.json()["items"]
    assert len(items) == 3
    assert [it["instrument_id"] for it in items] == [tcs_id, infy_id, rel_id]

    # Reorder items: RELIANCE first, then TCS, then INFY
    reorder_res = await client.patch(
        f"/api/v1/watchlists/{wl_id}/items/reorder",
        json={"instrument_ids": [rel_id, tcs_id, infy_id]},
    )
    assert reorder_res.status_code == 200
    reordered_items = reorder_res.json()["items"]
    assert [it["instrument_id"] for it in reordered_items] == [rel_id, tcs_id, infy_id]
    assert [it["position"] for it in reordered_items] == [0, 1, 2]

    # Invalid reorder: missing an instrument -> 400 Bad Request
    bad_reorder = await client.patch(
        f"/api/v1/watchlists/{wl_id}/items/reorder",
        json={"instrument_ids": [rel_id, tcs_id]},
    )
    assert bad_reorder.status_code == 400

    # Remove INFY
    del_item = await client.delete(f"/api/v1/watchlists/{wl_id}/items/{infy_id}")
    assert del_item.status_code == 204

    # Verify INFY removed
    get_after_del = await client.get(f"/api/v1/watchlists/{wl_id}")
    remaining = get_after_del.json()["items"]
    assert len(remaining) == 2
    assert infy_id not in [it["instrument_id"] for it in remaining]

    # Remove non-existent item in watchlist -> 404
    del_nonexistent = await client.delete(f"/api/v1/watchlists/{wl_id}/items/{infy_id}")
    assert del_nonexistent.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_error_handling(client: AsyncClient):
    # Nonexistent watchlist -> 404
    res = await client.get("/api/v1/watchlists/999999")
    assert res.status_code == 404

    # Add item to nonexistent watchlist -> 404
    res = await client.post("/api/v1/watchlists/999999/items", json={"instrument_id": 1})
    assert res.status_code == 404

    # Add nonexistent instrument -> 404
    wl = await client.post("/api/v1/watchlists", json={"name": "Error Test"})
    wl_id = wl.json()["id"]
    res = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": 999999})
    assert res.status_code == 404

    # Validation error: empty name -> 422
    res = await client.post("/api/v1/watchlists", json={"name": ""})
    assert res.status_code == 422
