

import logging
import re
from typing import Optional

from fastapi import APIRouter, Header, UploadFile, File, HTTPException,Form, Depends, Request
from openai import AsyncOpenAI
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/models", tags=["models"])


async def get_list_of_models(client: AsyncOpenAI):
    """
    Fetches the list of available models from the OpenAI API.
    """
    try:
        response = await client.models.list()
        return [model.id for model in response.data]
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch models from OpenAI API")
    
@router.get("/")
async def list_models(req: Request, x_api_key: Optional[str] = Header(None)):
    client: Optional[AsyncOpenAI] = (
        AsyncOpenAI(api_key=x_api_key) if x_api_key else req.app.state.openai_client
    )
    if client is None:
        return {"openai": []}

    try:
        response = await client.models.list()
        return {"openai": [model.id for model in response.data]}
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch models from OpenAI API")