from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
from openai import images
from app.utils.extract_table import download_image_from_s3
from PIL import Image
from io import BytesIO
import logging
import mlflow
import asyncio 
import redis.asyncio as redis
from app.schema.payload import TableExtractionRequestPayload, TablePayload, EovExtractionPayload
from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from app.schema.table import TablesResult
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Optional, List
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import random
import pandas as pd
import pymupdf
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import base64

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/extract", tags=["extract"])

@router.post("/metadata")
async def extract(
    req: Request,
    payload: EovExtractionPayload,
    semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    ):
  
    mlflow_client=req.app.state.mlflow_client
    if mlflow_client is None:
        raise HTTPException(status_code=503, detail="MLflow client not available")
    prompt_uri = payload.model.prompt_uri
    prompt_name="metadata"
    prompt:mlflow.entities.model_registry.PromptVersion= mlflow.genai.load_prompt(name_or_uri=f"prompts:/{prompt_name}@ref")
    langchain_prompt = ChatPromptTemplate.from_messages(
    prompt.to_single_brace_format()
    )  
    llm_params=payload.model.model_dump()
    model_params=llm_params.copy()
    model_params.pop("prompt_uri", None)  # remove if exists
    llm = ChatOpenAI(**model_params)
    
    source = payload.source
    hash_sha1 = payload.hash
    
    logger.info(f"Starting extraction with type:source: {source}, hash: {hash_sha1}")
    response_format = MetadataSchemaCIOOS
    text=payload.text
    
    
    with mlflow.start_run() as run:
        run_id=run.info.run_id
        # Use log_param instead of set_tag
        mlflow_client.link_prompt_version_to_run(run_id, prompt)
        mlflow.log_param("type", "metadata")
        if source:
            mlflow.log_param("source", source)
        if hash_sha1:
            mlflow.log_param("document_hash", hash_sha1)
       
        @mlflow.trace(name=f"main-metadata")
        async def run_for_eov_metadata(params):
            llm = ChatOpenAI(**params)
            local_chain = langchain_prompt | llm.with_structured_output(response_format)
            result =(await local_chain.ainvoke({"text": text})).model_dump()
            
            @mlflow.trace(name=f"assessment-metadata",span_type="LLM")
            def trace_one_by_one(eov: dict):
                return None
                # Trace each EOV one by one if the citations exist
            for eov in result.get("liste_eov") or [result]:
                trace_one_by_one(eov)
            return result
        seeds = [random.randint(0, 10000000) for _ in range(payload.runs)]
        coros = [run_for_eov_metadata({**model_params, "seed": seed}) for seed in seeds]
        
        results = [await coros[0]]
        
    return {"results": results, "run_id": run_id, "type": "metadata"}




@router.post("/eov")
async def extract(
    req: Request,
    payload: EovExtractionPayload,
    semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    ):
    logger.info(f"Received EOV extraction request for with payload: {payload}")
    hash_sha1 = payload.hash
    source = payload.source
    opensearch_client=req.app.state.opensearch_client
    mlflow_client=req.app.state.mlflow_client
    if mlflow_client is None:
        raise HTTPException(status_code=503, detail="MLflow client not available")
    prompt_uri = payload.model.prompt_uri
    prompt_name="eov"
    prompt:mlflow.entities.model_registry.PromptVersion= mlflow.genai.load_prompt(name_or_uri=f"prompts:/{prompt_name}@ref")
    langchain_prompt = ChatPromptTemplate.from_messages(
    prompt.to_single_brace_format()
    )  
    llm_params=payload.model.model_dump()
    model_params=llm_params.copy()
    model_params.pop("prompt_uri", None)  # remove if exists
    llm = ChatOpenAI(**model_params)
    if source:
        logger.info(f"Source provided: {source}")
    if hash_sha1:
        logger.info(f"Hash provided: {hash_sha1}")
    # logger.info(f"Starting extraction for session_id: {session_id} with type:source: {source}, hash: {hash_sha1}")
    response_format = EOVWithCitations
    text=payload.text
    with mlflow.start_run() as run:
        run_id=run.info.run_id
        # Use log_param instead of set_tag
        mlflow_client.link_prompt_version_to_run(run_id, prompt)
        mlflow.log_param("type", "eov")
        if source:
            mlflow.log_param("source", source)
        if hash_sha1:
            mlflow.log_param("document_hash", hash_sha1)
        
       
        @mlflow.trace(name=f"main-eov")
        async def run_for_eov_metadata(params):
            llm = ChatOpenAI(**params)
            local_chain = langchain_prompt | llm.with_structured_output(response_format)
            result =(await local_chain.ainvoke({"text": text})).model_dump()
            
            @mlflow.trace(name=f"assessment-eov",span_type="LLM")
            def trace_one_by_one(eov: dict):
                return None
                # Trace each EOV one by one if the citations exist
            for eov in result.get("liste_eov") or [result]:
                
                trace_one_by_one(eov)  # note: pass the copy, not the original
            return result
        seeds = [random.randint(0, 10000000) for _ in range(payload.runs)]
        coros = [run_for_eov_metadata({**model_params, "seed": seed}) for seed in seeds]
        if payload.runs > 1:
            results = await asyncio.gather(*coros, return_exceptions=True)

        else:
            results = [await coros[0]]
      
    return {"results": results, "run_id": run_id, "type": "eov"}


def render_pages(pdf_bytes: bytes, pages: list[int], dpi: int = 300) -> list[str]:
    """Blocking PyMuPDF work: returns base64 PNGs."""
    images = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for p in pages:
            if not 1 <= p <= doc.page_count:
                logger.warning(f"Page {p} out of range ({doc.page_count} pages).")
                continue
            png = doc[p - 1].get_pixmap(dpi=dpi).tobytes("png")
           
            images.append(base64.b64encode(png).decode("ascii"))
    return images

@router.post("/table")
async def extract_table(
    req: Request,
    payload: TableExtractionRequestPayload,
    semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10))
):
    logger.info(f"Received table extraction request for with payload: {payload}")
    mlflow.set_experiment("observia_table_extraction")
    if not payload.pages:
        raise HTTPException(status_code=400, detail="No pages provided for table extraction.")
    if not payload.hash:
        raise HTTPException(status_code=400, detail="No document hash provided for table extraction.")
    if not payload.model.provider:
        raise HTTPException(status_code=400, detail="No model provider specified for table extraction.")
    redis_client: redis.Redis = req.app.state.redis_client
    pdf_bytes = await redis_client.hget(f"doc:{payload.hash}", "pdf_bytes")   # hget, not get
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF bytes not found in Redis for the provided hash.")
    # Don't block the event loop with rendering
    images= await asyncio.to_thread(render_pages, pdf_bytes, payload.pages)
    if not images:
        raise HTTPException(400, "None of the requested pages exist in the document.")

    model_params=payload.model.model_dump().copy()
    llm = None
    

    # Use the model parameters from the payload
    if payload.model.provider == "openai":
        model_params.pop("provider", None)  # Remove provider key for OpenAI
        model_params.pop("prompt_uri", None)  # Remove prompt_uri if it exists
        model_params.update({"model": payload.model.model_name})
        llm = ChatOpenAI(**model_params)
        
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported model provider: {payload.model.provider}")
    if llm is not None:
        messages = [
                SystemMessage(content="You extract tables from document images accurately. "
                                      "Preserve headers and cell values exactly. Also extract the normalizedbounding boxes of each table and cell in the format: "),
                HumanMessage(content=[
                    {"type": "text", "text": "Extract the tables from the following document images with bounding boxes."},
                    *[
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}}
                        for b64 in images
                    ],
                ]),
            ]
        structured_llm = llm.with_structured_output(TablesResult)
        async with semaphore:
            result: TablesResult = await structured_llm.ainvoke(messages)
            result_dict = result.model_dump()
            bbox=result_dict.get("bbox", [])
            if bbox:
                result_dict["bbox"] = [bbox['x0'], bbox['y0'], bbox['x1'], bbox['y1']] if isinstance(bbox, dict) else bbox
        return {"results":result_dict, "run_id": None, "type": "table"}
    return HTTPException(status_code=500, detail="Failed to initialize LLM for table extraction.")
    