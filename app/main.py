import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Request
from dotenv import load_dotenv

from app.api.detect_sensitive import router as sensitive_router

load_dotenv()
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tokenizer = None
    app.state.model = None

    # async def _load():
    #     try:
    #         app.state.tokenizer, app.state.model = await asyncio.to_thread(load_model)
            
    #     except Exception:
    #         logger.exception("Model loading failed")
    # task = asyncio.create_task(_load())
    yield
    # task.cancel()

def create_app(test: bool = False) -> FastAPI:
    app = FastAPI(
        title="Sensitive Data Extraction API",
        version="1.0",
        description="API for extracting and searching information from PDFs using OCR and call APIs.",
        debug=test,
        lifespan=lifespan,
    )
    

    @app.get("/health")
    async def health_check(request: Request):
        return {"status": "ok", "model_loaded": request.app.state.model is not None}


    app.include_router(sensitive_router)

    return app




app = create_app()