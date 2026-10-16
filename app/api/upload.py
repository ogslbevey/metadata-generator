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
from typing import Any
from app.utils.text_utils import preprocess_text
from app.tasks import celery_app
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import group
import time
router = APIRouter(prefix="/upload", tags=["upload"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TTL_SECONDS = 60*60*24  # 24 hours


def send_ocr_tasks_for_pdf(
    pdf_url: str,
    hash_: str,
    batches: list[list[int]],
    total_pages: int,
    ocr: bool = False
) -> str:
    sigs = []
    for batch in batches:
        
        sig = celery_app.signature(
            "app.tasks.ocr.pdf",
            kwargs={"url": pdf_url, "hash": hash_,
                    "ocr": ocr, "pages": batch, "total_pages": total_pages},
            options={"queue": "ocr"},
        )
        sigs.append(sig)
        
    group_result = group(sigs).apply_async()
    group_result.save()
    return group_result.id
    



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

    if not file and not url:
        raise HTTPException(status_code=400, detail="You must provide either a file or a url.")
    if file and url:
        raise HTTPException(status_code=400, detail="Provide either file or url, not both.")

    s3_client = req.app.state.s3_client
    redis_client=req.app.state.redis_client
    semaphore = asyncio.Semaphore(max_concurrency)
 
    pdf_bytes = (
        await load_pdf_bytes_from_url(app=req.app, file=file)
        if file
        else await load_pdf_bytes_from_url(app=req.app, url=url)
    )
    
    hash_sha1 = hashlib.sha256(pdf_bytes).hexdigest()[:12]
    document_key = f"doc:{hash_sha1}"
    logger.info(f"Storing PDF in Redis: {document_key}")
    await redis_client.hset(
    document_key,
    mapping={"pdf_bytes": pdf_bytes}
    )
    await redis_client.expire(document_key, TTL_SECONDS)
   
    source = url if url else file.filename
    bucket = os.getenv("AWS_BUCKET_NAME")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages=doc.page_count
    
    if end_page is None:
        end_page = total_pages
    if not (1 <= start_page <= end_page <= total_pages):
        raise HTTPException(status_code=400, detail=f"Invalid page range {start_page}-{end_page} (document has {total_pages} pages).")

   
    
    args = {
        "s3_client": s3_client,
        "pdf_bytes": pdf_bytes,
        "hash_": hash_sha1,
        "sem": semaphore,
        "zoom_x": zoom_x,
        "zoom_y": zoom_y,
        "expires_in": expires_in,
        "bucket": bucket
        
    }
    args_for_pdf_upload = {
        "s3_client": s3_client,
        "pdf_bytes": pdf_bytes,
        "hash_": hash_sha1,
        "bucket": bucket
    }
    upload_pdf_res=None
    if file:
        logger.info(f"Uploading PDF to S3 for file: {file.filename}")
        try:
            upload_pdf_res=await upload_pdf_to_s3(**args_for_pdf_upload)
            logger.info(f"Uploading PDF to S3 for file: {upload_pdf_res}")
        except Exception as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
   
    try:
        pdf_url = None
        if file and upload_pdf_res and "url" in upload_pdf_res:
            pdf_url=upload_pdf_res.get("url")

        else:
            pdf_url=url
        
        batches = [
                list(range(i, min(i + pages_per_batch, end_page + 1)))
                for i in range(start_page, end_page + 1, pages_per_batch)
            ]
        
        logger.info(f"Sending OCR tasks for PDF: {pdf_url}, hash: {hash_sha1}, total_pages: {total_pages}, batches: {batches}")
        group_id_ocr=send_ocr_tasks_for_pdf(pdf_url=pdf_url, hash_=hash_sha1, batches=batches,total_pages=total_pages)
        return {"ocr_task": group_id_ocr,"hash": hash_sha1,"total_pages": total_pages}

    finally:
            logger.info(f"Closing document: {document_key}")
            doc.close()

class UploadResponse(BaseModel):
    hash: str
    pages:list[int]
    dpi:int=150

BUCKET = os.environ["AWS_BUCKET_NAME"]

@router.post("/image")
async def upload_images(req: Request, payload: UploadResponse):
    redis_client = req.app.state.redis_client
    s3_client = req.app.state.s3_client

    pdf_bytes = await redis_client.hget(f"doc:{payload.hash}", "pdf_bytes")
    if not pdf_bytes:
        raise HTTPException(404, "PDF not found in Redis. Please upload the PDF first.")

    scale = payload.dpi / 72.0
    logger.info(f"Rendering images for hash {payload.hash} at scale {scale} (DPI: {payload.dpi})")
    semaphore = asyncio.Semaphore(10)
    image_bytes = list(render_pages(pdf_bytes, page_indexes=payload.pages, zoom_x=scale, zoom_y=scale, img_type="png"))
    logger.info(f"Rendered images for hash {payload.hash}: {len(image_bytes)}")
    async def process(page: int,image_bytes: bytes) -> dict[str, str]:
    
        return await upload_get_url(
            s3_client, bucket=BUCKET,
            key=f"{payload.hash}/images/page-{page}.png",
            data=image_bytes, content_type="image/png",
            semaphore=semaphore, page_number=page,
        )

    results = await asyncio.gather(*(process(p,i) for p,i in zip(payload.pages,image_bytes)))
    logger.info(f"Uploaded images for hash {payload.hash}: {results}")
    urls = {k: v for r in results for k, v in r.items()}
    return {"hash": payload.hash, "urls": urls}
    

