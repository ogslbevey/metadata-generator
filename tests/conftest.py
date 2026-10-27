
import os
os.environ["REDIS_URL"] = "redis://default:local-redis-password@localhost:6379/0"
from app.main import create_app, lifespan
from httpx import AsyncClient, ASGITransport
import pytest_asyncio

import os

# Must be set before importing the app; setdefault lets CI override it
os.environ.setdefault("REDIS_URL", "redis://default:local-redis-password@localhost:6379/0")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app, lifespan


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app():
    application = create_app()
    async with lifespan(application):  # opens Redis, S3, etc.
        yield application


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


