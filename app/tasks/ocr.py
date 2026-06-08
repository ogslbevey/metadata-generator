from app.celery_app import celery_app
import logging
import httpx
import pymupdf
import fitz
import io
import pymupdf4llm
import json
import copy
import asyncio 
from img2table.ocr import TesseractOCR
from img2table.document import Image
from io import BytesIO
import pandas as pd
import redis
import os
from collections import OrderedDict

_redis = redis.Redis.from_url(os.getenv("REDIS_URL"))
_PDF_TTL = 3600  # match your result_expires
_pdf_cache: OrderedDict[str, bytes] = OrderedDict()
_CACHE_MAX = 3  # how many different docs to keep per process
logger = logging.getLogger(__name__)

boxes_to_choose=["text","section-header","table","caption"]
keys_to_remove = [
    "size",
    "flags",
    "bidi",
    "char_flags",
    "font",
    "color",
    "alpha",
    "ascender",
    "descender",
    "origin",
    "dir",
    "line"
]

def get_pdf_bytes(hash: str, url: str) -> bytes:
    if hash in _pdf_cache:
        _pdf_cache.move_to_end(hash)
        return _pdf_cache[hash]

    cached = _redis.hget(f"doc:{hash}", "pdf_bytes")   # hget, not get
    if cached:
        _pdf_cache[hash] = cached
        _pdf_cache.move_to_end(hash)
        return cached

    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    pdf_bytes = resp.content

    # fallback store must ALSO be hset, to keep the type consistent
    _redis.hset(f"doc:{hash}", mapping={"pdf_bytes": pdf_bytes})
    _redis.expire(f"doc:{hash}", _PDF_TTL)

    while len(_pdf_cache) >= _CACHE_MAX:
        _pdf_cache.popitem(last=False)
    _pdf_cache[hash] = pdf_bytes
    return pdf_bytes

@celery_app.task(
    bind=True,
    name="app.tasks.ocr.pdf",
)
def get_pdf_layout(self, url: str, hash: str, pages: list, total_pages: int) -> dict:
    pages_decrement = [page - 1 for page in pages]
    doc = None
    pdf_bytes = get_pdf_bytes(hash, url)
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        md = pymupdf4llm.to_json(
            doc,
            pages=pages_decrement,
            header=False,
            footer=False,
            ocr_language="eng+fra",
            force_ocr=True,
        )

        layout = json.loads(md)
        layout_pages = layout.get("pages", []) or []
        pages_cleaned = copy.deepcopy(layout_pages)

        for page in pages_cleaned:
            page.pop("fulltext", None)
            page.pop("words", None)
            page.pop("links", None)

            for box in page.get("boxes", []) or []:
                for k in ("x0", "y0", "x1", "y1"):
                    box.pop(k, None)
                table = box.get("table")
                if table is not None:
                    table.pop("markdown", None)
                for textline in box.get("textlines", []) or []:
                    textline.pop("bbox", None)
                    for span in textline.get("spans", []) or []:
                        for key in keys_to_remove:
                            span.pop(key, None)

        return {                      
            "url": url,
            "status": "SUCCESS",
            "type": "pymupdf4llm",
            "hash": hash,
            "layout": pages_cleaned,
        }

    except Exception as e:
        logger.error(f"Error processing PDF {url}: {e}")
        raise
    finally:
        if doc:
            doc.close()

   
    
            


    




