from __future__ import annotations
from dataclasses import dataclass
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional
from fastapi import FastAPI
import logging
import httpx
from app.deps.redis_init import init_redis, close_redis
from app.deps.mlflow_init import setup_mlflow
from app.deps.psql_init  import init_pg_pool, close_pg_pool
from typing import Callable, Awaitable, TypeVar, Any, ParamSpec
import os
import asyncio
import functools
import aioboto3
from openai import AsyncOpenAI

import mlflow 
from opensearchpy import AsyncOpenSearch
from botocore.config import Config

logger=logging.getLogger(__name__)
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
    
# All resource initialization and cleanup in one place
@dataclass
class Resources:
    redis_client: object | None
    mlflow_client: object | None
    pg_pool: object | None
    s3_client: object | None
    gemini_client: object | None
    openai_client: object | None
    http_client: object | None = None
    opensearch_client: object | None = None

@asynccontextmanager
async def resource_lifespan(app: Optional[FastAPI] = None):
    resources = Resources(
        redis_client=None,
        mlflow_client=None,
        pg_pool=None,
        s3_client=None,
        gemini_client=None,
        openai_client=None,
        http_client=None,
        opensearch_client=None
    )

    s3_context = None

    try:
        resources.redis_client = init_redis()
        resources.mlflow_client=setup_mlflow()
        session = aioboto3.Session()
        logger.info("Initializing S3 client...")
        logger.info(f"AWS_ENDPOINT_URL: {os.getenv('AWS_ENDPOINT_URL')}")
      
        s3_context = session.client(
            "s3",
            endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name="us-east-1",
            config=Config(
                
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 3},
            ),
        )
        resources.s3_client = await s3_context.__aenter__()
        
        resources.openai_client=AsyncOpenAI()
        resources.http_client= httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=30.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
        )
        resources.opensearch_client=AsyncOpenSearch(
        hosts=[{"host":os.environ.get("OPENSEARCH_HOST"), "port": int(os.environ.get("OPENSEARCH_PORT"))}],
        http_auth=("admin", os.environ.get("OPENSEARCH_PASSWORD")),
        use_ssl=False,
        verify_certs=False,      # demo self-signed cert; set True + ca_certs in prod
        ssl_show_warn=False) 
     

        logger.info(await resources.opensearch_client.info())
        if app is not None:
            app.state.s3_client = resources.s3_client
            app.state.redis_client = resources.redis_client
            app.state.pg_pool = resources.pg_pool
            app.state.openai_client=resources.openai_client
            app.state.http_client=resources.http_client
            app.state.gemini_client=resources.gemini_client
            app.state.mlflow_client=resources.mlflow_client
            app.state.opensearch_client=resources.opensearch_client
           
        yield resources

    finally:
        if s3_context is not None:
            await s3_context.__aexit__(None, None, None)

        if resources.redis_client is not None:
            await close_redis(resources.redis_client)

        if resources.pg_pool is not None:
            await close_pg_pool(resources.pg_pool)

        if resources.gemini_client is not None:
            await resources.gemini_client.aio.aclose()

        if resources.http_client is not None:
            await resources.http_client.aclose()

        if resources.opensearch_client is not None:
            await resources.opensearch_client.close()


P = ParamSpec("P")
R = TypeVar("R")
def with_resources(
    fn: Callable[P, Awaitable[R]]
) -> Callable[P, R]:
    """
    Decorate an *async* function so it runs inside resource_lifespan()
    and becomes callable from a sync Typer command.
    The decorated function will receive `resources` as a kwarg.
    """
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        async def _runner() -> R:
            async with resource_lifespan() as resources:
                # pass resources as a keyword to avoid arg-order headaches
                return await fn(*args, **kwargs, resources=resources)

        return asyncio.run(_runner())

    return wrapper