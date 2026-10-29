from aiohttp import ClientError
from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
import uuid
import fitz
import hashlib
import json
import os
import logging
import asyncio
from app.utils.parser import load_pdf_bytes_from_url
from fastapi.responses import StreamingResponse
from app.utils.bucket_uploader import render_pages,upload_pdf_to_s3,generate_presigned_url_for_image,upload_get_url
from app.utils.local_storage import LOCAL_STORAGE_DIR, save_pdf_to_volume
from typing import Any
from app.utils.text_utils import preprocess_text
from app.tasks import celery_app
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import group
import time
import os
import asyncio
from pathlib import Path

router = APIRouter(prefix="/upload", tags=["upload"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TTL_SECONDS = 60*60*24  # 24 hours


def send_ocr_tasks_for_pdf(
    s3_url: dict,
    hash_: str,
    batches: list[list[int]],
    total_pages: int,
    ocr: bool = False
   
) -> str:
    sigs = []
    for batch in batches:
        
        sig = celery_app.signature(
            "app.tasks.ocr.pdf",
            kwargs={"hash": hash_,
                    "ocr": ocr, "pages": batch, "total_pages": total_pages, "s3_url": s3_url},
            options={"queue": "ocr"},
        )
        sigs.append(sig)
        
    group_result = group(sigs).apply_async()
    group_result.save()
    return group_result.id



async def _fetch_pages(redis_client, doc_hash: str, page_numbers: list[int]) -> dict[int, dict]:
    """Read saved page layouts from Redis in one round trip."""
    async with redis_client.pipeline(transaction=False) as pipe:  # read-only, no MULTI needed
        for n in page_numbers:
            pipe.get(f"doc:{doc_hash}:page:{n}")
        values = await pipe.execute()

    pages = {n: json.loads(v) for n, v in zip(page_numbers, values) if v is not None}
    missing = set(page_numbers) - pages.keys()
    if missing:
        logger.warning("Pages missing in Redis for %s: %s", doc_hash, sorted(missing))
    return pages


@router.post("/pdf")
async def upload_pdf(
    req: Request,
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    start_page: int = Form(1),
    end_page: int | None = Form(None),
    pages_per_batch: int = Form(20),
    max_concurrency: int = Form(50),
    zoom_x: float = Form(3.0),
    zoom_y: float = Form(3.0),
    expires_in: int = Form(60 * 60 * 24),
    ocr_force: bool = Form(False),
):
    s3_bucket=os.environ.get("AWS_BUCKET_NAME")
    s3_client=req.app.state.s3_client
    logger.info(f"Using S3 bucket: {s3_bucket}")
    if not file and not url:
        raise HTTPException(status_code=400, detail="You must provide either a file or a url.")
    if file and url:
        raise HTTPException(status_code=400, detail="Provide either file or url, not both.")

    logger.info("Using Redis client")
    
  
 
    pdf_bytes = (
        await load_pdf_bytes_from_url(app=req.app, file=file)
        if file
        else await load_pdf_bytes_from_url(app=req.app, url=url)
    )
    
    hash_sha1 = hashlib.sha256(pdf_bytes).hexdigest()
    semaphore = asyncio.Semaphore(max_concurrency)
    if s3_bucket:
        s3_url = await upload_pdf_to_s3(
            s3_client, pdf_bytes, hash_=hash_sha1, bucket=s3_bucket, TTL_SECONDS=expires_in
        )
        s3_url["storage"] = "s3"
    else:
        logger.info(f"No S3 bucket configured, saving to volume: {LOCAL_STORAGE_DIR}")
        s3_url = await save_pdf_to_volume(pdf_bytes, hash_=hash_sha1)
    document_key = f"doc:{hash_sha1}"   
    logger.info(f"Storing PDF in Redis: {document_key}")
   
    source = url if url else file.filename
   
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages=doc.page_count
    
    if end_page is None:
        end_page = total_pages
    if not (1 <= start_page <= end_page <= total_pages):
        raise HTTPException(status_code=400, detail=f"Invalid page range {start_page}-{end_page} (document has {total_pages} pages).")
    

    requested = list(range(start_page, end_page + 1))
    # ocr_force asks for a fresh OCR run, so cached text-extraction results don't count
    cached = {} if ocr_force else await  _fetch_pages(req.app.state.redis_client, hash_sha1, requested)
    missing = [p for p in requested if p not in cached]

    response = {"hash": hash_sha1, "total_pages": total_pages,
                "s3_url": s3_url.get("url"), "key": s3_url.get("key"), "pages": cached}
    try:
        if not missing:
            logger.info(f"All {len(requested)} pages cached for {document_key}, skipping OCR")
            return {**response, "ocr_task": None}

        batches = [missing[i:i + pages_per_batch] for i in range(0, len(missing), pages_per_batch)]
        group_id_ocr = send_ocr_tasks_for_pdf(hash_=hash_sha1, batches=batches,
                                              total_pages=total_pages, s3_url=s3_url, ocr=ocr_force)
        return {**response, "ocr_task": group_id_ocr}
    finally:
        logger.info(f"Closing document: {document_key}")
        doc.close()

