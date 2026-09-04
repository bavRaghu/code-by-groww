import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.seed import seed_dev_data


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with AsyncSessionLocal() as session:
        await seed_dev_data(session)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
