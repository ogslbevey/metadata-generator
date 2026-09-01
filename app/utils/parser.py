import pymupdf
from fastapi import UploadFile, File, Form, HTTPException, APIRouter, Request, FastAPI
import logging
import httpx
import asyncio
from contextlib import nullcontext
import fitz 

from app.utils.sensitive_utils import detect_phone_numbers, detect_email_addresses, detect_canadian_postal_codes
import pandas as pd 
import threading
import re
from typing import List, Dict, Any
import json
import copy
import logging
logger=logging.getLogger(__name__)

#To load PDF bytes from either a URL or an uploaded file
async def load_pdf_bytes_from_url(
    url: str | None = None,
    file: UploadFile | None = None,
    app: FastAPI | None = None,
    client: httpx.AsyncClient | None = None,
    fetch_sem: asyncio.Semaphore | None = None,
) -> bytes:
    if file is not None:
        return await file.read()

    if not url:
        raise HTTPException(status_code=400, detail="url or file required")

    resolved_client = client or (getattr(app.state, "http_client", None) if app else None)
    resolved_sem = fetch_sem or (getattr(app.state, "fetch_sem", None) if app else None)

    owns_client = resolved_client is None
    if resolved_client is None:
        resolved_client = httpx.AsyncClient(timeout=30.0)

    sem_context = resolved_sem if resolved_sem is not None else nullcontext()

    BROWSER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
        "Referer": str(httpx.URL(url).copy_with(path="/")),
    }

    RETRYABLE_STATUS = {429, 500, 502, 503, 504}
    last_exc = None

    try:
        for attempt in range(4):
            try:
                async with sem_context:
                    resp = await resolved_client.get(url, headers=BROWSER_HEADERS)
                logger.info(f"{resp.headers.get("server")} {resp.headers.get("cf-ray") }{resp.status_code} {url} (attempt {attempt + 1})")
                # Handle HTTP errors explicitly before retrying
                if resp.status_code == 403:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Remote server denied access to PDF (403 Forbidden): {url}",
                    )
                if resp.status_code not in RETRYABLE_STATUS:
                    resp.raise_for_status()  # 404, 410, etc. — fail immediately
                elif resp.status_code in RETRYABLE_STATUS:
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    if attempt == 3:
                        break
                    await asyncio.sleep(0.25 * (2 ** attempt))
                    continue

                return resp.content

            except HTTPException:
                raise  # Don't swallow clean HTTP exceptions
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt == 3:
                    break
                await asyncio.sleep(0.25 * (2 ** attempt))

        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch PDF after retries: {type(last_exc).__name__}",
        )
    finally:
        if owns_client:
            await resolved_client.aclose()


# ocr_lock = threading.Lock()
# boxes_to_choose=["text","section-header","table","caption"]
# keys_to_remove = [
#     "size",
#     "flags",
#     "bidi",
#     "char_flags",
#     "font",
#     "color",
#     "alpha",
#     "ascender",
#     "descender",
#     "origin",
#     "dir",
#     "line"
# ]
# def extract_markdown_text(pdf_bytes: bytes, page_indexes: list[int]) -> list[dict]:
#     doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#     try:
#         with ocr_lock:
#             md = pymupdf4llm.to_json(
#                 doc,
#                 pages=page_indexes,
#                 header=False,
#                 footer=False,
#                 # ocr_language="eng+fra",
#                 # force_ocr=True
#             )

#             layout = json.loads(md)
#             pages = layout.get("pages", []) or []
#             pages_cleaned = copy.deepcopy(pages)
#             text=""
#             for page in pages_cleaned:
#                 fulltext=page.pop("fulltext",None)
#                 words=page.pop("words",None)
#                 links=page.pop("links",None)

#                 for box in page.get("boxes",[]) or []:
#                     box.pop("x0",None)
#                     box.pop("y0",None)
#                     box.pop("x1",None)
#                     box.pop("y1",None)
#                     table=box.get("table",None)
#                     if table is not None:
#                         # table.pop("cells",None)
#                         table.pop("markdown",None)
#                         # table.pop("bbox",None)
                        
#                     for textline in box.get("textlines",[]) or []:
#                         textline.pop("bbox",None)
                        
#                         for span in textline.get("spans",[]) or []:
#                             for key in keys_to_remove:
#                                 span.pop(key,None)
                        
#             return pages_cleaned
#     finally:
#         doc.close()






# def extract_markdown_text(pdf_bytes: bytes, page_index: int) -> dict:
#     doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#     try:
#         md = pymupdf4llm.to_markdown(doc, pages=[page_index],header=False, footer=False)
#         text=doc.load_page(page_index).get_text()
#         result={
#             "page": page_index + 1,
#             "md": md,
#             "text": text
#         }
#         phone_numbers = detect_phone_numbers(text)
#         email_addresses = detect_email_addresses(text)
#         postal_codes = detect_canadian_postal_codes(text)
#         if len(phone_numbers) > 0 or len(email_addresses) > 0 or len(postal_codes) > 0:
#             result["sensitive_info"] = {
#                 "phone_numbers": phone_numbers,
#                 "email_addresses": email_addresses,
#                 "postal_codes": postal_codes
#             }
#         return result

#     finally:
#         doc.close()

