import asyncio
import logging
import os

import mlflow
from fastapi import APIRouter, HTTPException, Request
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from mlflow import MlflowClient
from app.api.list_models import get_pricing
from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from app.schema.payload import ExtractionPayload, ExtractionTypes, ModelParameters
from app.schema.table import TablesResult
from app.utils.ai_utils import load_prompt
from app.utils.bucket_uploader import load_pdf_bytes, render_and_upload_pages,upload_pdf_bytes_from_s3
from mlflow.entities import AssessmentSource, AssessmentSourceType, SpanType
import pandas as pd 
from app.utils.local_storage import load_pdf_bytes_from_volume, render_pages_to_volume, image_data_url
router = APIRouter(prefix="/extract", tags=["extract"])
logger = logging.getLogger(__name__)

# One shared limit on concurrent LLM calls across all requests
LLM_SEMAPHORE = asyncio.Semaphore(10)

# Keys containing these words are never logged or put into traces
SECRET_MARKERS = ("key", "token", "secret")

SCHEMAS = {
    ExtractionTypes.eov: EOVWithCitations,
    ExtractionTypes.metadata: MetadataSchemaCIOOS,
    ExtractionTypes.table: TablesResult,
}

# The client does not use MLflow's per-thread "active run" stack,
# so concurrent requests on the same event loop no longer collide.
mlflow_client = MlflowClient()


# ─── Helpers ─────────────────────────────────────────────────────────────────


def safe_params(params: ModelParameters) -> dict:
    """Model parameters without API keys or other secrets."""
    return {
        k: v for k, v in params.to_llm().items()
        if not any(m in k.lower() for m in SECRET_MARKERS)
    }


def get_chat_model(params: ModelParameters):
    logger.info("Initializing chat model with parameters: %s", safe_params(params))
    if params.provider == "openai":
        return ChatOpenAI(**params.to_llm())
    if params.provider == "anthropic":
        return ChatAnthropic(**params.to_llm())
    if params.provider == "google":
        return ChatGoogleGenerativeAI(**params.to_llm())
    raise HTTPException(400, f"Unsupported model provider: {params.provider}")





def iter_items(parsed):
    """EOV results are a list under liste_eov; metadata and table results are a single object."""
    if hasattr(parsed, "liste_eov"):
        return parsed.liste_eov or []
    
    return [parsed]



def build_text_calls(payload: ExtractionPayload, extraction_type: ExtractionTypes) -> list[dict]:
    """Metadata / EOV: every model gets the same text prompt."""
    if not payload.text:
        raise HTTPException(400, f"'text' is required for {extraction_type.value} extraction.")
    if not payload.model:
        raise HTTPException(400, f"'model' is required for {extraction_type.value} extraction.")

    messages = [
        {"role": "system", "content": load_prompt(extraction_type.value)},
        {"role": "user", "content": payload.text},
    ]
    return [{"params": p, "messages": messages} for p in payload.model]

async def build_table_calls(req: Request, payload: ExtractionPayload) -> tuple[list[dict], dict]:
    """Table: one call per page, each with only its own page image."""
    if not payload.pages:
        raise HTTPException(400, "'pages' is required for table extraction.")
    if not payload.hash:
        raise HTTPException(400, "'hash' is required for table extraction.")

    bucket = os.environ.get("AWS_BUCKET_NAME")
    if bucket:
        logger.info("Loading PDF %s from S3 bucket %s", payload.hash, bucket)
        semaphore = asyncio.Semaphore(10)
        try:
            pdf_bytes = await upload_pdf_bytes_from_s3(req.app.state.s3_client, bucket, payload.hash, semaphore)
        except Exception:
            raise HTTPException(404, "PDF not found in S3. Please upload the PDF first.")
        urls = await render_and_upload_pages(
            pdf_bytes, payload.hash, payload.pages, payload.dpi, req.app.state.s3_client, bucket
        )
        llm_urls = urls  # presigned URLs: the provider downloads them itself
    else:
        logger.info("No S3 bucket configured, loading PDF %s from volume", payload.hash)
        try:
            pdf_bytes = await load_pdf_bytes_from_volume(payload.hash)
        except FileNotFoundError:
            raise HTTPException(404, "PDF not found on volume. Please upload the PDF first.")
        try:
            paths = await render_pages_to_volume(pdf_bytes, payload.hash, list(payload.pages.keys()), payload.dpi)
        except ValueError as e:
            raise HTTPException(400, str(e))
        urls = {p: f"file://{path}" for p, path in paths.items()}
        # The provider can't read our disk, so send the image inline
        llm_urls = await asyncio.to_thread(lambda: {p: image_data_url(path) for p, path in paths.items()})

    system = {"role": "system", "content": load_prompt(ExtractionTypes.table.value)}
    calls = []
    for page, params in payload.pages.items():
        page_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract all tables from the following page"},
                {"type": "image_url", "image_url": {"url": llm_urls[str(page)]}},
            ],
        }
        calls.append({
            "params": params,
            "messages": [system, page_message],
            "page": page,
            "hash": payload.hash,
            "url": urls[str(page)],  # short path/URL for the trace input
        })
    return calls, urls

async def run_chain(
    params: ModelParameters,
    schema,
    messages: list,
    extraction_type: ExtractionTypes,
    page: int | None = None,
    hash: str | None = None,
    url: str | None = None,
) -> dict:
    # Same shape for every outcome; page is None for text extractions
    if page is not None:
        results={}
    else:
        results=[]
    @mlflow.trace(name=f"main-{extraction_type.value}", span_type=SpanType.LLM)
    async def traced_main(input,hash,type=extraction_type.value):
        # The main span is opened BEFORE the LLM call, so the autologged
        # LangChain spans (RunnableSequence, ChatOpenAI, ...) nest under it.
        trace_id=mlflow.get_current_active_span().trace_id
        @mlflow.trace(name=f"assessment-{extraction_type.value}", span_type=SpanType.LLM)
        def assess_item(input):
            logger.info("Assessing item: %s", input)
            span_id=mlflow.get_current_active_span().span_id
            if page is not None:
                results[page]={**input.model_dump(), "trace_id":trace_id, "span_id":span_id}
            else:
                results.append({**input.model_dump(), "trace_id":trace_id, "span_id":span_id})
            return None
                    
        try:
            chain = get_chat_model(params).with_structured_output(schema, include_raw=True)
            async with LLM_SEMAPHORE:  # hold the slot only for the LLM call
                raw_result = await chain.ainvoke(messages)
                
                usage_metadata=raw_result.get("usage_metadata", {})
                parsed=raw_result.get("parsed", {})
                logger.info("Parsed result: %s", parsed)
                iterated_items=iter_items(parsed)
                logger.info("Iterated items: %s", iterated_items)
                for item in iterated_items:

                    assess_item(item)
                return raw_result
        except Exception as e:
            logger.exception("Model %s failed", params.model)
            return None, str(e), None, None, None
    if url:
        await traced_main(input=url,hash=hash)
    else:
        await traced_main(input=messages[-1]["content"] if messages else None,hash=hash)
    return results

@router.post("/{extraction_type}")
async def extract(req: Request, extraction_type: ExtractionTypes, payload: ExtractionPayload):
    schema = SCHEMAS[extraction_type]
    urls = None
    if extraction_type == ExtractionTypes.table:
        calls, urls = await build_table_calls(req, payload)
    else:
        calls = build_text_calls(payload, extraction_type)

    logger.info("Starting %s extraction with %d calls", extraction_type.value, len(calls))
    logger.info(payload.hash)

    results = await asyncio.gather(*(
        run_chain(
            call["params"],
            schema,
            call["messages"],
            extraction_type,
            page=call.get("page"),
            hash=payload.hash,
            url=call.get("url"),
        )
        for call in calls
    ))

    if extraction_type == ExtractionTypes.table:
        # Merge {page: result} dicts into one dict keyed by page
        by_page = {}
        for r in results:
            by_page.update({str(page): value for page, value in r.items()})
        response = {"type": extraction_type.value, "results": by_page}
    else:
        flat = [item for sublist in results for item in sublist]
        response = {
            "type": extraction_type.value,
            "results": pd.DataFrame(flat).to_dict(orient="split"),
        }

    if urls is not None:
        response["urls"] = urls
    return response