import os
from fastapi import FastAPI, Depends, Request

from contextlib import asynccontextmanager
from app.api import upload,mlflow_res,detect_sensitive,extract,search,ocr_tasks,search
from app.logging_config import LOG_CONFIG
import logging.config
import mlflow
from mlflow import MlflowClient
import httpx
import asyncio
import os

from app.core.context import resource_lifespan
from fastapi.middleware.cors import CORSMiddleware
logger = logging.getLogger(__name__)
logging.config.dictConfig(LOG_CONFIG)


# origins = os.getenv("CORS_ORIGINS").split(",")
# logger.info(f"CORS origins set to: {origins}")
#Define lifespan event handlers for startup and shutdown of the app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=True,
    )
    app.state.fetch_sem = asyncio.Semaphore(10)
    app.state.pdf_fetch_sem = asyncio.Semaphore(5)

    # Initialize resources
    async with resource_lifespan(app) as resources:
        yield  # Run the app
    # Resources will be cleaned up after this block
    await app.state.http_client.aclose()

def create_app(test: bool = False) -> FastAPI:
    app = FastAPI(
        title="Grand Extractor API",
        version="1.0",
        description="API for extracting and searching information from PDFs using OCR and call APIs.",
        debug=test,
        lifespan=lifespan
    )
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=origins,
    #     allow_credentials=True,
    #     allow_methods=["*"],
    #     allow_headers=["*"],
    # )
    # app.include_router(chat.router)
    app.include_router(upload.router)
    app.include_router(mlflow_res.router)
    app.include_router(detect_sensitive.router)
    app.include_router(extract.router)
    app.include_router(search.router)
    app.include_router(ocr_tasks.router)
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    return app

app = create_app()

