from app.main import create_app, lifespan
from httpx import AsyncClient, ASGITransport
import pytest_asyncio
import pytest

@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(base_url="http://test", transport=transport) as ac:
            yield ac
@pytest_asyncio.fixture
async def app():
    app = create_app()
    async with lifespan(app):
        yield app
# BACKEND_URL = "https://grand-extracteur-backend-production.up.railway.app"
# @pytest_asyncio.fixture
# async def client():
#     async with AsyncClient(
#         base_url=BACKEND_URL,
#         timeout=400,
#     ) as ac:
#         yield ac



