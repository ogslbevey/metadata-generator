import asyncio
import logging

import mlflow
from fastapi import APIRouter, HTTPException, Request
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from app.schema.payload import ExtractionPayload, ExtractionTypes, ModelParameters
from app.utils.ai_utils import load_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extract", tags=["extract"])

# One shared limit on concurrent LLM calls across all requests
LLM_SEMAPHORE = asyncio.Semaphore(10)

# Keys containing these words are never logged or put into traces
SECRET_MARKERS = ("key", "token", "secret")


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
    raise HTTPException(400, f"Unsupported model provider: {params.provider}")


def assess(data: dict, extraction_type: ExtractionTypes) -> dict:
    """One assessment span per extracted item, nested under the model's main span."""
    with mlflow.start_span(
        name=f"assessment-{extraction_type.value}", span_type="EVALUATOR"
    ) as span:
        span.set_inputs(data)
        result = {}  # TODO: your assessment logic here
        span.set_outputs(result)
        return result


def iter_items(parsed):
    """EOV results are a list under liste_eov; metadata results are a single object."""
    if hasattr(parsed, "liste_eov"):
        return parsed.liste_eov or []
    return [parsed]


async def run_chain(
    params: ModelParameters,
    schema,
    messages: list,
    extraction_type: ExtractionTypes,
) -> dict:
    entry = {
        "provider": params.provider,
        "model": params.model,
        "served_model": None,
        "output": None,
        "usage_metadata": {},
        "error": None,
        "trace_id": None,
    }

    # The main span is opened BEFORE the LLM call, so the autologged
    # LangChain spans (RunnableSequence, ChatOpenAI, ...) nest under it.
    with mlflow.start_span(
        name=f"main-{extraction_type.value}-{params.model}", span_type="CHAIN"
    ) as span:
        entry["trace_id"] = span.trace_id  # MLflow 2.x: span.request_id
        span.set_inputs({"model_params": safe_params(params), "messages": messages})

        # Building the model inside the span means a bad config fails only this model
        try:
            chain = get_chat_model(params).with_structured_output(schema, include_raw=True)
            async with LLM_SEMAPHORE:  # hold the slot only for the LLM call
                raw_result = await chain.ainvoke(messages)
        except Exception as e:
            logger.exception("Model %s failed", params.model)
            entry["error"] = str(e)
            span.set_status("ERROR")
            span.set_outputs(entry)
            return entry

        raw = raw_result["raw"]
        meta = raw.response_metadata or {}
        entry["served_model"] = meta.get("model_name") or meta.get("model")
        entry["usage_metadata"] = dict(raw.usage_metadata or {})
        span.set_attributes({
            "usage": entry["usage_metadata"],
            "served_model": entry["served_model"],
            "finish_reason": meta.get("finish_reason") or meta.get("stop_reason"),
        })

        parsed = raw_result["parsed"]
        if raw_result["parsing_error"] or parsed is None:
            entry["error"] = str(raw_result["parsing_error"] or "No parsed output")
            logger.error("Model %s parsing failed: %s", params.model, entry["error"])
            span.set_status("ERROR")
            span.set_outputs(entry)
            return entry

        for item in iter_items(parsed):
            assess(item.model_dump(), extraction_type)

        entry["output"] = parsed.model_dump()
        span.set_outputs(entry)
        return entry


@router.post("/{extraction_type}")
async def extract(req: Request, extraction_type: ExtractionTypes, payload: ExtractionPayload):
    schema = EOVWithCitations if extraction_type == ExtractionTypes.eov else MetadataSchemaCIOOS

    user_content = (
        f"Extract the following pages: {payload.pages} from the document."
        if payload.pages else payload.text
    )
    messages = [
        {"role": "system", "content": load_prompt(extraction_type.value)},
        {"role": "user", "content": user_content},
    ]
    logger.info("Starting extraction of type %s with %d models", extraction_type.value, len(payload.model))
    with mlflow.start_run() as run:
        mlflow.log_param("extraction_type", extraction_type.value)
        if payload.source:
            mlflow.log_param("source", payload.source)
        if payload.hash:
            mlflow.log_param("document_hash", payload.hash)

        # run_chain catches its own errors, so every model returns an entry
        results = await asyncio.gather(
            *(run_chain(p, schema, messages, extraction_type) for p in payload.model)
        )

    return {
        "type": extraction_type.value,
        "run_id": run.info.run_id,
        "results": results,
    }