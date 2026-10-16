import asyncio
import functools
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar

import aioboto3
import httpx
import mlflow
from aiobotocore.config import AioConfig
from dotenv import load_dotenv
from fastapi import FastAPI
from opensearchpy import AsyncOpenSearch

from app.deps.mlflow_init import setup_mlflow
from app.deps.redis_init import close_redis, init_redis
from app.tasks import celery_app

load_dotenv()  # Load environment variables from .env file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    logger.info("%s is %s", key, "set" if os.environ.get(key) else "not set")


@dataclass
class Resources:
    redis_client: Any | None = None
    mlflow_client: Any | None = None
    pg_pool: Any | None = None
    s3_client: Any | None = None
    http_client: Any | None = None
    opensearch_client: Any | None = None
    celery_app: Any | None = None
    phoenix_client: Any | None = None


@asynccontextmanager
async def resource_lifespan(app: Optional[FastAPI] = None):
    resources = Resources(celery_app=celery_app)

    # The exit stack keeps the S3 client open until shutdown and closes it
    # automatically, even if a later resource fails to initialize.
    async with AsyncExitStack() as stack:
        try:
            resources.redis_client = init_redis()
            resources.mlflow_client = setup_mlflow()

            # --- S3 / MinIO ---
            session = aioboto3.Session()
            resources.s3_client = await stack.enter_async_context(
            session.client(
                "s3",
                endpoint_url=os.getenv("AWS_ENDPOINT_URL"),  # https://bucket-production-a541.up.railway.app
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                config=AioConfig(
                signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required",
                    connect_timeout=5,
                    read_timeout=30,
                    retries={"max_attempts": 3},
                ),
            )
            )
            # --- HTTP client ---
            resources.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=30.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                follow_redirects=True,
            )

            # --- OpenSearch ---
            use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "true").lower() in ("1", "true", "yes")
            resources.opensearch_client = AsyncOpenSearch(
                hosts=[{
                    "host": os.environ.get("OPENSEARCH_HOST"),
                    "port": int(os.environ.get("OPENSEARCH_PORT", "9200")),
                }],
                http_auth=("admin", os.environ.get("OPENSEARCH_PASSWORD")),
                use_ssl=use_ssl,
                verify_certs=False,  # demo self-signed cert; set True + ca_certs in prod
                ssl_show_warn=False,
            )
            logger.info(await resources.opensearch_client.info())

            if app is not None:
                app.state.s3_client = resources.s3_client
                app.state.redis_client = resources.redis_client
                app.state.http_client = resources.http_client
                app.state.mlflow_client = resources.mlflow_client
                app.state.opensearch_client = resources.opensearch_client
                app.state.celery_app = resources.celery_app

            logger.info("Resources initialized successfully.")
            yield resources  # the ONLY yield: app / CLI command runs here

        finally:
            try:
                mlflow.flush_trace_async_logging(terminate=True)
            except Exception:
                logger.exception("Failed to flush MLflow traces")

            if resources.redis_client is not None:
                await close_redis(resources.redis_client)

            if resources.http_client is not None:
                await resources.http_client.aclose()

            if resources.opensearch_client is not None:
                await resources.opensearch_client.close()
        # S3 client is closed here by the exit stack


P = ParamSpec("P")
R = TypeVar("R")


def with_resources(fn: Callable[P, Awaitable[R]]) -> Callable[P, R]:
    """
    Decorate an *async* function so it runs inside resource_lifespan()
    and becomes callable from a sync Typer command.
    The decorated function will receive `resources` as a kwarg.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        async def _runner() -> R:
            async with resource_lifespan() as resources:
                return await fn(*args, **kwargs, resources=resources)

        return asyncio.run(_runner())

    return wrapper