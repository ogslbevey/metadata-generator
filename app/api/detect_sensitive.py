from fastapi import APIRouter, HTTPException
from app.utils.sensitive_utils import detect_phone_numbers, detect_email_addresses, detect_canadian_postal_codes
from pydantic import BaseModel
import logging 
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detect", tags=["sensitive"])

class SensitiveRequest(BaseModel):
    text: str

@router.post("/sensitive_info")
async def detect_sensitive_info(payload: SensitiveRequest):
    text = payload.text

    phone_numbers = detect_phone_numbers(text)
    email_addresses = detect_email_addresses(text)
    postal_codes = detect_canadian_postal_codes(text)
    # logger.info(text)
    # logger.info(repr(text))
    return {
        "phone_numbers": phone_numbers,
        "email_addresses": email_addresses,
        "postal_codes": postal_codes
    }