
from app.celery_app import celery_app
import os
import json 
from urllib.parse import urlparse
from app.celery_app import redis_client as r
import gc
import json
import logging
import pymupdf
import pymupdf4llm
import requests
from pathlib import Path
from app.celery_app import redis_client as r
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
DOC_TTL_SECONDS = 60 * 60 * 24
LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "/data/pdfs")).resolve()


def _page_key(doc_hash: str, page: int) -> str:
    return f"doc:{doc_hash}:page:{page}"


def _index_key(doc_hash: str) -> str:
    return f"doc:{doc_hash}:pages"


def save_pages(doc_hash: str, page_layouts: list[dict]) -> list[int]:
    index_key = _index_key(doc_hash)
    pipe = r.pipeline(transaction=True)
    saved = []
    for layout in page_layouts:
        page = layout["page_number"]
        key = _page_key(doc_hash, page)
        pipe.set(key, json.dumps(layout), ex=DOC_TTL_SECONDS)  # value + TTL atomically
        pipe.zadd(index_key, {key: page})                       # sorted by page number
        saved.append(page)
    pipe.expire(index_key, DOC_TTL_SECONDS)                     # after zadd, so the key exists
    pipe.execute()
    logger.info("Saved %d pages for doc %s: %s", len(saved), doc_hash, saved)
    return saved




def _check_pdf(data: bytes, source: str) -> bytes:
    if not data.startswith(b"%PDF"):
        raise ValueError(f"Not a PDF: {source}")
    return data


def read_pdf_from_volume(path_str: str) -> bytes:
    path = Path(path_str).resolve()
    # Only allow files inside the storage dir (protects against path traversal)
    if not path.is_relative_to(LOCAL_STORAGE_DIR):
        raise ValueError(f"Path outside storage dir: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found on volume: {path}")
    return _check_pdf(path.read_bytes(), str(path))


def fetch_pdf_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=(5, 60))  # (connect, read) seconds
    response.raise_for_status()
    return _check_pdf(response.content, url)


def load_pdf_bytes(source: dict) -> bytes:
    url = source.get("url") or ""
    path = source.get("path")
    logger.info(f"Loading PDF from source: {source}")
    if source.get("storage") == "local" or path or url.startswith("file://"):
        return read_pdf_from_volume(path or urlparse(url).path)

    if url.startswith(("http://", "https://")):
        return fetch_pdf_bytes(url)

    raise ValueError(f"Unsupported PDF source: {source}")



@celery_app.task(bind=True, name="app.tasks.ocr.pdf")
def get_pdf_layout(self,  hash: str, pages: list, s3_url: dict,
                   total_pages: int, ocr: bool = False) -> dict:
    page_indexes = [page - 1 for page in pages]
    doc = None
    try:
        url=s3_url.get("url")
        if not url:
            raise ValueError("S3 URL is missing in the payload.")
        pdf_bytes = load_pdf_bytes(s3_url)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        del pdf_bytes  # the document holds its own data from here on

        md = pymupdf4llm.to_json(
            doc,
            pages=page_indexes,
            header=False,
            footer=False,
            ocr_language="eng+fra",
            force_ocr=ocr,
        )
        layout_pages = json.loads(md).get("pages", []) or []
        del md
        saved = save_pages(hash, layout_pages)

        return {
           
            "status": "SUCCESS",
            "type": "pymupdf4llm",
            "hash": hash,
            "layout": layout_pages,
        }

    except Exception:
        logger.exception("Error processing PDF %s", hash)
        raise

    finally:
        if doc is not None:
            doc.close()
        pymupdf.TOOLS.store_shrink(100)  # empty MuPDF's internal cache
        gc.collect()


