from functools import lru_cache
from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
from openai import images
from app.utils.extract_table import download_image_from_s3
from PIL import Image
from io import BytesIO
import logging
import mlflow
import asyncio 
import redis.asyncio as redis
from app.schema.payload import ExtractionPayload, ModelParameters,ExtractionTypes
from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from app.schema.table import TablesResult
from app.utils.ai_utils import generate_text_openai
from typing import Optional, List
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import AsyncCallbackHandler
import random
import pandas as pd
from app.utils.token_count import system_prompt_tokens
from pathlib import Path
import base64
from app.utils.ai_utils import load_prompt
import httpx
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/extract", tags=["extract"])


def get_chat_model(params: ModelParameters):
    logger.info(f"Initializing chat model with parameters: {params.to_llm()}")
    if params.provider == "openai":
        return ChatOpenAI(**params.to_llm())
    if params.provider == "anthropic":
        return ChatAnthropic(**params.to_llm())
    raise HTTPException(400, f"Unsupported model provider: {params.provider}")

# Module level: one shared limit across all requests
LLM_SEMAPHORE = asyncio.Semaphore(10)


async def run_chain(chain, messages):
    async with LLM_SEMAPHORE:          # limits each individual LLM call
        return await chain.ainvoke(messages)


def raw_results_to_results(raw_results: list[dict],payload: ExtractionPayload,extraction_type: ExtractionTypes) -> list[dict]:
    results = []
    with mlflow.start_run() as run:
        run_id=run.info.run_id
        if payload.source:
            mlflow.log_param("source", payload.source)
        if payload.hash:
            mlflow.log_param("document_hash", payload.hash)
        mlflow.log_param("extraction_type", extraction_type.value)
        for params, res in zip(payload.model, raw_results):
            entry = {"provider": params.provider, "model": params.model,
                    "output": None, "usage_metadata": {}, "error": None}

            if isinstance(res, Exception):
                logger.error("Model %s failed: %r", params.model, res)
                entry["error"] = str(res)
            else:
                entry["usage_metadata"] = dict(res["raw"].usage_metadata or {})
                if res["parsing_error"] or res["parsed"] is None:
                    logger.error("Model %s parsing failed: %r", params.model, res["parsing_error"])
                    entry["error"] = str(res["parsing_error"] or "No parsed output")
                else:
                    entry["output"] = res["parsed"].model_dump()
                    logger.info(f"Model {params.model} output: {entry['output']}")

                @mlflow.trace(name=f"main-{extraction_type.value}",span_type="LLM")
                def trace_main(usage_metadata: dict,model_params: ModelParameters=params):
                    @mlflow.trace(name=f"assessment-{extraction_type.value}",span_type="LLM")
                    def trace_one_by_one(data: dict):
                        return None
                    if isinstance(entry['output'], dict) and "liste_eov" not in entry['output']:
                        trace_one_by_one(entry['output'])
                    else:
                        for eov in entry["output"]["liste_eov"] or [entry["output"]]:
                            logger.info("Tracing EOV: %s", eov)
                            trace_one_by_one(eov.copy())  # note: pass the copy, not the original
                    return None
                    
                trace_main(entry["usage_metadata"], params)
            results.append(entry)
    return results,run_id

@router.post("/{extraction_type}")
async def extract(req: Request, extraction_type: ExtractionTypes, payload: ExtractionPayload):
   
    mlflow_client = req.app.state.mlflow_client
    schema = EOVWithCitations if extraction_type == ExtractionTypes.eov else MetadataSchemaCIOOS
    loaded_prompt = load_prompt(extraction_type.value)
    
    user_content = (
        f"Extract the following pages: {payload.pages} from the document."
        if payload.pages else payload.text
    )
    messages = [
        {"role": "system", "content": loaded_prompt},
        {"role": "user", "content": user_content},
    ]
    
    chains = [
        get_chat_model(p).with_structured_output(schema, include_raw=True)
        for p in payload.model
    ]
    raw_results = await asyncio.gather(
        *(run_chain(c, messages) for c in chains), return_exceptions=True
    )
    logger.info(f"Raw results: {raw_results}")
    results,run_id = raw_results_to_results(raw_results, payload, extraction_type)
    logger.info(f"Run ID: {run_id}")

    return {"type": extraction_type.value,"run_id": run_id, "results": results}
