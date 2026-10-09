from functools import lru_cache
import os

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pyparsing import Optional
from app.schema.eov import EOVWithCitations
from app.schema.metadata import MetadataSchemaCIOOS
from mlflow.client import MlflowClient
from mlflow.entities.model_registry import PromptVersion
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
import pymupdf 
import mlflow 
import logging
import httpx
from pathlib import Path
import base64
from app.schema.payload import ModelParameters
from pydantic import BaseModel
import copy
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompts"


class UsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int

def load_prompt_from_mlflow(prompt_name: str, **variables) -> str:
    """Load a prompt from MLflow and return the final system prompt text."""
    # try:
    #     prompt = mlflow.genai.load_prompt(f"prompts:/{prompt_name}@ref", cache_ttl_seconds=3600)
    #     if prompt.variables:  # e.g. {{domain}} placeholders
    #         return prompt.format(**variables)
    #     return prompt.template  # no variables, use the text as is
    # except Exception as e:
    #     logger.error(f"Error loading prompt from MLflow: {e}")
    #     return (PROMPT_DIR / "v1" / f"{prompt_name}.txt").read_text(encoding="utf-8")
    raise mlflow.exceptions.MlflowException("MLflow is not configured. Please set the MLFLOW_TRACKING_URI environment variable.")

@lru_cache(maxsize=32)
def load_prompt(prompt_name: str, **variables) -> str:
    # """Load a prompt from MLflow and return the final system prompt text."""
    # try:
    #     return load_prompt_from_mlflow(prompt_name, **variables)
    # except Exception as e:
    #     logger.error(f"Error loading prompt: {e}")
    return (PROMPT_DIR /"v1" / f"{prompt_name}.txt").read_text(encoding="utf-8")



def make_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a Pydantic JSON schema into one accepted by OpenAI strict mode."""
    schema = copy.deepcopy(schema)
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node

        # A $ref with sibling keys (e.g. description) isn't allowed: inline the definition
        if "$ref" in node and len(node) > 1:
            name = node["$ref"].split("/")[-1]
            merged = {**defs[name], **{k: v for k, v in node.items() if k != "$ref"}}
            return walk(merged)

        node.pop("default", None)

        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])

        return {key: walk(value) for key, value in node.items()}

    return walk(schema)

async def generate_text_openai(
    http: httpx.AsyncClient,
    messages: list[dict],
    schema_model: type[BaseModel],
    model_parameters: ModelParameters,
    prompt_name: str | None = "eov",
    **variables,
) -> tuple[str, UsageInfo]:
    if prompt_name:
        prompt = load_prompt(prompt_name, **variables)
        if isinstance(prompt, str):
            messages = [{"role": "system", "content": prompt}] + messages
        else:
            messages = list(prompt) + messages

    body = {
        **model_parameters.to_openai(),   # model, temperature, and any extras
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_model.__name__,
                "schema": make_strict(schema_model.model_json_schema()),
                "strict": True,
            },
        },
    }

    r = await http.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json=body,
        timeout=120,
    )
    if r.is_error:
        logger.error("OpenAI API error %s: %s", r.status_code, r.text)
        r.raise_for_status()
    data= r.json()
    usage_data=data.get("usage", {})
    usage_info = {
        "input_tokens": usage_data.get("prompt_tokens", 0),
        "output_tokens": usage_data.get("completion_tokens", 0),
        "total_tokens": usage_data.get("total_tokens", 0),
        "cached_tokens": usage_data.get("prompt_token_details", {}).get("cached_tokens", 0),
    }
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage_info = UsageInfo(**usage_info)
    return content,usage_info



  

