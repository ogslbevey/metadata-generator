from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
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
from app.schema.table import TableSchema
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Optional, List
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import random
import pandas as pd
from app.api.search import search


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


# @router.post("/metadata/{session_id}")
# async def extract(
 
#     session_id: str,
#     req: Request,
#     payload: EovExtractionPayload,
#     semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    
#     ):
#     logger.info(f"Received EOV extraction request for session_id: {session_id} with payload: {payload}")
#     r: redis.Redis = req.app.state.redis_client
#     mlflow_client=req.app.state.mlflow_client
#     if mlflow_client is None:
#         raise HTTPException(status_code=503, detail="MLflow client not available")
#     prompt_uri = payload.model.prompt_uri
#     prompt_name="metadata"
#     prompt:mlflow.entities.model_registry.PromptVersion= mlflow.genai.load_prompt(name_or_uri=f"prompts:/{prompt_name}@ref")
#     langchain_prompt = ChatPromptTemplate.from_messages(
#     prompt.to_single_brace_format()
#     )  
#     llm_params=payload.model.model_dump()
#     model_params=llm_params.copy()
#     model_params.pop("prompt_uri", None)  # remove if exists
#     llm = ChatOpenAI(**model_params)
#     key = f"session:{session_id}"
#     if not await r.exists(key):
#         raise HTTPException(status_code=404, detail="Session ID not found")
#     source = await r.hget(key, "source")
#     hash_sha1 = await r.hget(key, "hash")
    
#     logger.info(f"Starting extraction for session_id: {session_id} with type:source: {source}, hash: {hash_sha1}")
#     response_format = MetadataSchemaCIOOS
#     text=payload.text
    
    
#     with mlflow.start_run() as run:
#         run_id=run.info.run_id
#         # Use log_param instead of set_tag
#         mlflow_client.link_prompt_version_to_run(run_id, prompt)
#         mlflow.log_param("type", "metadata")
#         mlflow.log_param("source", source)
#         mlflow.log_param("document_hash", hash_sha1)
       
#         @mlflow.trace(name=f"main-metadata")
#         async def run_for_eov_metadata(params):
#             llm = ChatOpenAI(**params)
#             local_chain = langchain_prompt | llm.with_structured_output(response_format)
#             result =(await local_chain.ainvoke({"text": text})).model_dump()
            
#             @mlflow.trace(name=f"assessment-metadata",span_type="LLM")
#             def trace_one_by_one(eov: dict):
#                 return None
#                 # Trace each EOV one by one if the citations exist
#             for eov in result.get("liste_eov") or [result]:
#                 trace_one_by_one(eov)
#             return result
#         seeds = [random.randint(0, 10000000) for _ in range(payload.runs)]
#         coros = [run_for_eov_metadata({**model_params, "seed": seed}) for seed in seeds]
        
#         results = [await coros[0]]
#         await r.hset(
#             key,
#             mapping={
#                 "run_id": run_id,
#                 "type": "metadata",
#                 "hash": hash_sha1,
#                 "source": source,
#             },
#         )
#     return {"results": results, "run_id": run_id, "type": "metadata"}



@router.post("/eov")
async def extract(
    req: Request,
    payload: EovExtractionPayload,
    semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    ):
    # logger.info(f"Received EOV extraction request for session_id: {session_id} with payload: {payload}")
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


# @router.post("/eov/{session_id}")
# async def extract(
 
#     session_id: str,
#     req: Request,
#     payload: EovExtractionPayload,
#     semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    
#     ):
#     logger.info(f"Received EOV extraction request for session_id: {session_id} with payload: {payload}")
#     r: redis.Redis = req.app.state.redis_client
#     mlflow_client=req.app.state.mlflow_client
#     if mlflow_client is None:
#         raise HTTPException(status_code=503, detail="MLflow client not available")
#     prompt_uri = payload.model.prompt_uri
#     prompt_name="eov"
#     prompt:mlflow.entities.model_registry.PromptVersion= mlflow.genai.load_prompt(name_or_uri=f"prompts:/{prompt_name}@ref")
#     langchain_prompt = ChatPromptTemplate.from_messages(
#     prompt.to_single_brace_format()
#     )  
#     llm_params=payload.model.model_dump()
#     model_params=llm_params.copy()
#     model_params.pop("prompt_uri", None)  # remove if exists
#     llm = ChatOpenAI(**model_params)
#     key = f"session:{session_id}"
#     if not await r.exists(key):
#         raise HTTPException(status_code=404, detail="Session ID not found")
#     source = await r.hget(key, "source")
#     hash_sha1 = await r.hget(key, "hash")
    
#     logger.info(f"Starting extraction for session_id: {session_id} with type:source: {source}, hash: {hash_sha1}")
#     response_format = EOVWithCitations
#     text=payload.text
    
    
#     with mlflow.start_run() as run:
#         run_id=run.info.run_id
#         # Use log_param instead of set_tag
#         mlflow_client.link_prompt_version_to_run(run_id, prompt)
#         mlflow.log_param("type", "eov")
#         mlflow.log_param("source", source)
#         mlflow.log_param("document_hash", hash_sha1)
       
#         @mlflow.trace(name=f"main-eov")
#         async def run_for_eov_metadata(params):
#             llm = ChatOpenAI(**params)
#             local_chain = langchain_prompt | llm.with_structured_output(response_format)
#             result =(await local_chain.ainvoke({"text": text})).model_dump()
            
#             @mlflow.trace(name=f"assessment-eov",span_type="LLM")
#             def trace_one_by_one(eov: dict):
#                 return None
#                 # Trace each EOV one by one if the citations exist
#             for eov in result.get("liste_eov") or [result]:
                
#                 trace_one_by_one(eov)
#             return result
#         seeds = [random.randint(0, 10000000) for _ in range(payload.runs)]
#         coros = [run_for_eov_metadata({**model_params, "seed": seed}) for seed in seeds]
#         if payload.runs > 1:
#             results = await asyncio.gather(*coros, return_exceptions=True)
#         else:
#             results = [await coros[0]]
#         await r.hset(
#             key,
#             mapping={
#                 "run_id": run_id,
#                 "type": "eov",
#                 "hash": hash_sha1,
#                 "source": source,
#             },
#         )
#     return {"results": results, "run_id": run_id, "type": "eov"}

@router.post("/table/{session_id}")
async def extract_tables(
    session_id: str,
    req: Request,
    payload: TableExtractionRequestPayload,
    semaphore: Optional[asyncio.Semaphore] = Depends(lambda: asyncio.Semaphore(10)),
    
    ):
    data = []
    previous_table = None
    logger.info(len(payload.data))
    for item in payload.data:
        current_table = item
        current_col_count = len(current_table.table[0])

        last_col_count = (
            len(previous_table["table"][0]) if isinstance(previous_table, dict)
            else len(previous_table.table[0])
        ) if previous_table else None

        if (
            previous_table
            and current_table.caption == ''
            and current_col_count == last_col_count
        ):
            try:
                last_item = data.pop()

                if isinstance(last_item, pd.DataFrame):
                    last_df = last_item
                elif isinstance(last_item, dict):
                    last_df = pd.DataFrame(last_item["table"])
                else:
                    last_df = pd.DataFrame(last_item.table)

                current_df = pd.DataFrame(current_table.table)
                current_df.columns = last_df.columns

                merged_df = pd.concat([last_df, current_df], ignore_index=True)

                prev = previous_table if not isinstance(previous_table, dict) else None
                data.append({
                    "id": f"{previous_table.get('id', '') if isinstance(previous_table, dict) else previous_table.id}_{current_table.id}",
                    "page_number": f"{previous_table.get('page_number', '') if isinstance(previous_table, dict) else previous_table.page_number}_{current_table.page_number}",
                    "caption": previous_table.get("caption", "") if isinstance(previous_table, dict) else previous_table.caption,
                    "table": merged_df.values.tolist()
                })

            except Exception as e:
                logger.error(f"Error merging table {current_table.id}: {e}")
                data.append({"id": current_table.id, "page_number": current_table.page_number, "caption": current_table.caption, "table": current_table.table})
        else:
            data.append({"id": current_table.id, "page_number": current_table.page_number, "caption": current_table.caption, "table": current_table.table})

        previous_table = data[-1]  # ← always track the dict we just appended, not the raw object
    return {"results": data, "type": "table"}
       
