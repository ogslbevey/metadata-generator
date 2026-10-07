import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException,Request
from pydantic import BaseModel

from app.utils.sensitive_utils import (
    detect_canadian_postal_codes,
    detect_email_addresses,
    detect_phone_numbers,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detect", tags=["sensitive"])


class SensitiveRequest(BaseModel):
    hash: Optional[str] = None
    text:Optional[str] = None

@router.post("/sensitive_info")
async def detect_sensitive_info(request: Request, payload: SensitiveRequest):
    text = payload.text
    hash = payload.hash
    if not text and not hash:
        raise HTTPException(status_code=400, detail="Either 'text' or 'hash' must be provided.")
    if text:
        return {
            "phone_numbers": detect_phone_numbers(text),
            "email_addresses": detect_email_addresses(text),
            "postal_codes": detect_canadian_postal_codes(text),
        }
    