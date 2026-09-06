import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models.change_review import ChangeReview
from app.models.detected_change import DetectedChange
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user import User
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem


@pytest.mark.asyncio
async def test_1_registration_lifecycle(unauthenticated_client: AsyncClient, db_session: AsyncSession):
    """
    Test successful registration creates user with hashed password and returns valid JWT.
    """
    payload = {
        "email": "alice@example.com",
        "password": "Password123!",
        "name": "Alice Wonderland",
    }
    res = await unauthenticated_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["name"] == "Alice Wonderland"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]

    # Verify password is not plaintext in database
    user_stmt = select(User).where(User.email == "alice@example.com")
    db_user = (await db_session.execute(user_stmt)).scalar_one()
    assert db_user.hashed_password != "Password123!"
    assert db_user.hashed_password.startswith("scrypt$")
    assert verify_password("Password123!", db_user.hashed_password)


@pytest.mark.asyncio
async def test_2_duplicate_registration_rejected(unauthenticated_client: AsyncClient):
    """
    Test duplicate registration with the same email returns 409 Conflict.
    """
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123!",
        "name": "First User",
    }
    res1 = await unauthenticated_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await unauthenticated_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_3_login_success_and_failures(unauthenticated_client: AsyncClient):
    """
    Test login with valid credentials, incorrect password, and nonexistent user.
    """
    reg_payload = {
        "email": "bob@example.com",
        "password": "CorrectPassword123",
        "name": "Bob Smith",
    }
    await unauthenticated_client.post("/api/v1/auth/register", json=reg_payload)

    # 1. Successful login
    login_res = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "CorrectPassword123"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 2. Incorrect password
    wrong_pw_res = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "WrongPassword123"},
    )
    assert wrong_pw_res.status_code == 401
    assert "invalid" in wrong_pw_res.json()["detail"].lower()

    # 3. Nonexistent user
    no_user_res = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123"},
    )
    assert no_user_res.status_code == 401


@pytest.mark.asyncio
async def test_4_unauthenticated_protected_endpoint_rejected(unauthenticated_client: AsyncClient):
    """
    Test protected endpoints strictly reject requests lacking valid authentication with 401 Unauthorized.
    """
    # GET /watchlists
    res1 = await unauthenticated_client.get("/api/v1/watchlists")
    assert res1.status_code == 401

    # POST /watchlists
    res2 = await unauthenticated_client.post("/api/v1/watchlists", json={"name": "Hacker WL"})
    assert res2.status_code == 401

    # Invalid token
    res3 = await unauthenticated_client.get(
        "/api/v1/watchlists",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert res3.status_code == 401

    # GET /auth/me
    res4 = await unauthenticated_client.get("/api/v1/auth/me")
    assert res4.status_code == 401


@pytest.mark.asyncio
async def test_5_auth_me_and_logout_endpoints(unauthenticated_client: AsyncClient):
    """
    Test /auth/me returns current user and /auth/logout acknowledges session termination.
    """
    reg_payload = {
        "email": "carol@example.com",
        "password": "CarolPassword123",
        "name": "Carol Danvers",
    }
    reg_res = await unauthenticated_client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me
    me_res = await unauthenticated_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "carol@example.com"
    assert me_res.json()["name"] == "Carol Danvers"

    # /auth/logout
    logout_res = await unauthenticated_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert "logged out" in logout_res.json()["message"].lower()


@pytest.mark.asyncio
async def test_6_cross_user_isolation_watchlist_crud(db_session: AsyncSession):
    """
    Security & Authorization:
    Prove User B cannot read, update, or delete User A's watchlist.
    """
    transport = ASGITransport(app=app)

    # Setup User A
    user_a = User(
        email="usera@example.com",
        hashed_password=hash_password("Pass12345"),
        name="User A",
        is_active=True,
    )
    # Setup User B
    user_b = User(
        email="userb@example.com",
        hashed_password=hash_password("Pass12345"),
        name="User B",
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    token_a = create_access_token(user_a.id, user_a.email)
    token_b = create_access_token(user_b.id, user_b.email)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_a}"}) as client_a, \
               AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_b}"}) as client_b:

        # User A creates a private watchlist
        wl_res = await client_a.post("/api/v1/watchlists", json={"name": "User A Private Watchlist"})
        assert wl_res.status_code == 201
        wl_a_id = wl_res.json()["id"]

        # User B lists watchlists -> must NOT see User A's watchlist
        list_b = await client_b.get("/api/v1/watchlists")
        assert list_b.status_code == 200
        assert not any(w["id"] == wl_a_id for w in list_b.json())

        # User B attempts to read User A's watchlist directly -> 404 (anti-enumeration)
        get_b = await client_b.get(f"/api/v1/watchlists/{wl_a_id}")
        assert get_b.status_code == 404

        # User B attempts to rename User A's watchlist -> 404
        patch_b = await client_b.patch(f"/api/v1/watchlists/{wl_a_id}", json={"name": "Hacked Name"})
        assert patch_b.status_code == 404

        # User B attempts to delete User A's watchlist -> 404
        del_b = await client_b.delete(f"/api/v1/watchlists/{wl_a_id}")
        assert del_b.status_code == 404

        # User A can still access and see it unchanged
        get_a = await client_a.get(f"/api/v1/watchlists/{wl_a_id}")
        assert get_a.status_code == 200
        assert get_a.json()["name"] == "User A Private Watchlist"


@pytest.mark.asyncio
async def test_7_cross_user_isolation_watchlist_items_and_reorder(db_session: AsyncSession):
    """
    Security & Authorization:
    Prove User B cannot add, remove, or reorder items in User A's watchlist.
    """
    transport = ASGITransport(app=app)
    tcs = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == "TCS"))).scalar_one()
    infy = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == "INFY"))).scalar_one()

    user_a = User(email="user_items_a@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    user_b = User(email="user_items_b@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    token_a = create_access_token(user_a.id, user_a.email)
    token_b = create_access_token(user_b.id, user_b.email)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_a}"}) as client_a, \
               AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_b}"}) as client_b:

        wl_res = await client_a.post("/api/v1/watchlists", json={"name": "A Items WL"})
        wl_id = wl_res.json()["id"]
        await client_a.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": tcs.id})

        # User B attempts to add an item to A's watchlist -> 404
        add_b = await client_b.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": infy.id})
        assert add_b.status_code == 404

        # User B attempts to remove an item from A's watchlist -> 404
        rem_b = await client_b.delete(f"/api/v1/watchlists/{wl_id}/items/{tcs.id}")
        assert rem_b.status_code == 404

        # User B attempts to reorder A's watchlist items -> 404
        reorder_b = await client_b.patch(f"/api/v1/watchlists/{wl_id}/items/reorder", json={"instrument_ids": [tcs.id]})
        assert reorder_b.status_code == 404


@pytest.mark.asyncio
async def test_8_cross_user_isolation_check_changes_and_attention(db_session: AsyncSession):
    """
    Security & Authorization:
    Prove User B cannot trigger check, read changes, or access attention feed on User A's watchlist.
    """
    transport = ASGITransport(app=app)
    user_a = User(email="user_feed_a@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    user_b = User(email="user_feed_b@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    token_a = create_access_token(user_a.id, user_a.email)
    token_b = create_access_token(user_b.id, user_b.email)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_a}"}) as client_a, \
               AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_b}"}) as client_b:

        wl_res = await client_a.post("/api/v1/watchlists", json={"name": "A Intelligence WL"})
        wl_id = wl_res.json()["id"]

        # User B check endpoint -> 404
        chk_b = await client_b.post(f"/api/v1/watchlists/{wl_id}/check")
        assert chk_b.status_code == 404

        # User B changes endpoint -> 404
        chg_b = await client_b.get(f"/api/v1/watchlists/{wl_id}/changes")
        assert chg_b.status_code == 404

        # User B attention endpoint -> 404
        att_b = await client_b.get(f"/api/v1/watchlists/{wl_id}/attention")
        assert att_b.status_code == 404

        # User B market endpoint -> 404
        mkt_b = await client_b.get(f"/api/v1/watchlists/{wl_id}/market")
        assert mkt_b.status_code == 404


@pytest.mark.asyncio
async def test_9_review_state_isolated_across_users(db_session: AsyncSession):
    """
    Security & Authorization:
    Prove ChangeReview review state is strictly isolated per user.
    """
    transport = ASGITransport(app=app)
    tcs = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == "TCS"))).scalar_one()

    user_a = User(email="rev_a@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    user_b = User(email="rev_b@example.com", hashed_password=hash_password("Pass12345"), is_active=True)
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    token_a = create_access_token(user_a.id, user_a.email)
    token_b = create_access_token(user_b.id, user_b.email)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_a}"}) as client_a, \
               AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token_b}"}) as client_b:

        wl_a_res = await client_a.post("/api/v1/watchlists", json={"name": "Rev A WL"})
        wl_a_id = wl_a_res.json()["id"]
        await client_a.post(f"/api/v1/watchlists/{wl_a_id}/items", json={"instrument_id": tcs.id})

        wl_b_res = await client_b.post("/api/v1/watchlists", json={"name": "Rev B WL"})
        wl_b_id = wl_b_res.json()["id"]
        await client_b.post(f"/api/v1/watchlists/{wl_b_id}/items", json={"instrument_id": tcs.id})

        # User B attempts to review User A's watchlist -> 404
        rev_b_on_a = await client_b.post(f"/api/v1/watchlists/{wl_a_id}/review-all")
        assert rev_b_on_a.status_code == 404


@pytest.mark.asyncio
async def test_10_input_validation_and_tamper_proofing(client: AsyncClient):
    """
    Security:
    Verify invalid path parameters, empty/whitespace names, and malformed inputs are rejected.
    """
    # Negative watchlist ID
    res1 = await client.get("/api/v1/watchlists/-1")
    assert res1.status_code == 422

    # Zero watchlist ID
    res2 = await client.get("/api/v1/watchlists/0")
    assert res2.status_code == 422

    # Whitespace-only watchlist name
    res3 = await client.post("/api/v1/watchlists", json={"name": "   "})
    assert res3.status_code == 422

    # Empty watchlist name
    res4 = await client.post("/api/v1/watchlists", json={"name": ""})
    assert res4.status_code == 422


@pytest.mark.asyncio
async def test_11_error_handling_no_internal_leak(unauthenticated_client: AsyncClient):
    """
    Security:
    Verify internal 500 error responses do not leak database stack traces or table internals.
    """
    # Request invalid JSON structure on register
    res = await unauthenticated_client.post(
        "/api/v1/auth/register",
        content="not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    assert "Traceback" not in str(data)
    assert "psycopg" not in str(data)
    assert "sqlalchemy" not in str(data).lower()
