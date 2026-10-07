from app.celery_app import celery_app
import logging
import httpx
import pymupdf
import fitz
import io
import pymupdf4llm
import json
import copy
from io import BytesIO
import pandas as pd
from app.tasks.cache import get_pdf_bytes

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



@celery_app.task(
    bind=True,
    name="app.tasks.ocr.pdf",
)
def get_pdf_layout(self, url: str, hash: str, pages: list, total_pages: int,ocr: bool=False) -> dict:
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
            force_ocr=ocr,
        )
        
        layout = json.loads(md)
        layout_pages = layout.get("pages", []) or []
        

        return {                      
            "url": url,
            "status": "SUCCESS",
            "type": "pymupdf4llm",
            "hash": hash,
            "layout": layout_pages,
        }

    except Exception as e:
        logger.error(f"Error processing PDF {url}: {e}")
        raise
    finally:
        if doc:
            doc.close()

   
    
            


    




