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
SensitiveResults = dict[str, list[str] | None]

PII_LABELS = [
    "ACCOUNTNUM", "BUILDINGNUM", "CITY", "CREDITCARDNUMBER", "DATEOFBIRTH",
    "DRIVERLICENSENUM", "EMAIL", "GIVENNAME", "IDCARDNUM", "PASSWORD",
    "SOCIALNUM", "STREET", "SURNAME", "TAXNUM", "TELEPHONENUM",
    "USERNAME", "ZIPCODE",
]


class SensitiveRequest(BaseModel):
    text:Optional[str] = None
    model_name: Optional[str] = None

@router.post("/sensitive_info")
async def detect_sensitive_info(request: Request, payload: SensitiveRequest):
    text = payload.text
   
    model_name = payload.model_name
    if not text and not hash:
        raise HTTPException(status_code=400, detail="Either 'text' or 'hash' must be provided.")
    found = {
        "TELEPHONENUM": detect_phone_numbers(text),
        "EMAIL": detect_email_addresses(text),
        "ZIPCODE": detect_canadian_postal_codes(text),
    }
    return {label: values for label, values in found.items() if values}