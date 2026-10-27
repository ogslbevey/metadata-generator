

import logging
import re
from typing import Optional
from pathlib import Path
import json
from fastapi import APIRouter, Header, UploadFile, File, HTTPException,Form, Depends, Request

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/models", tags=["models"])
REGISTRY_PATH = Path(__file__).parent.parent.parent / "models.json"
from typing import Optional


def select_tier(tiers: list[dict], input_tokens: int) -> dict:
    """Pick the first tier whose limit fits the prompt size. null = no limit."""
    sorted_tiers = sorted(
        tiers,
        key=lambda t: t["max_input_tokens"] if t["max_input_tokens"] is not None else float("inf"),
    )
    for tier in sorted_tiers:
        limit = tier["max_input_tokens"]
        if limit is None or input_tokens <= limit:
            return tier
    raise HTTPException(status_code=400, detail="Input exceeds all pricing tiers.")


def get_pricing(
    input_tokens: int,
    output_tokens: int,
    model_name: str,
    cached_tokens: int = 0,
    batch: bool = False,
):
    if not REGISTRY_PATH.exists():
        raise HTTPException(status_code=500, detail="models.json file not found.")

    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)

    model_info = registry["models"].get(model_name)
    if not model_info or not model_info.get("enabled", True):
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found.")

    per_tokens = registry.get("per_tokens", 1_000_000)
    tier = select_tier(model_info["tiers"], input_tokens)

    # cached tokens are part of input_tokens but billed at the cache_read rate
    cache_rate = tier["cache_read"] if tier["cache_read"] is not None else tier["input"]
    uncached = input_tokens - cached_tokens

    input_cost = (uncached * tier["input"] + cached_tokens * cache_rate) / per_tokens
    output_cost = output_tokens * tier["output"] / per_tokens
    total_cost = input_cost + output_cost

    if batch and model_info.get("batch_discount"):
        total_cost *= 1 - model_info["batch_discount"]
    
    return {
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "tier_max_input_tokens": tier["max_input_tokens"],
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "currency": registry.get("currency", "USD"),
    }

def get_list_of_models(image_supported: Optional[str] = None) -> list[dict]:
    if not REGISTRY_PATH.exists():
        raise HTTPException(status_code=500, detail="models.json file not found.")

    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)

    model_list = []
    for model_name, model_info in registry["models"].items():
        if not model_info.get("enabled", True):
            continue
        if image_supported is not None:
            image_input = model_info.get("image_input", False)
            if (image_supported.lower() == "true" and not image_input) or (
                image_supported.lower() == "false" and image_input
            ):
                continue
        model_list.append(
           model_name
        )
    return model_list

def get_list_of_models(image_supported: Optional[bool] = None) -> list[str]:
    registry = json.loads(REGISTRY_PATH.read_text())
    return [
        model_id
        for model_id, info in registry["models"].items()
        if info.get("enabled", True)
        and (image_supported is None or info["image_input"] == image_supported)
    ]

@router.get("/")
async def list_models(req: Request):
    """
    Endpoint to list available models. Optionally filter by a query string.
    """
   
    models = get_list_of_models(image_supported=True)
    text_only_models = get_list_of_models(image_supported=False)
    return {"image_supported": models, "text_only": text_only_models}

    