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
from app.utils.bucket_uploader import render_and_upload, upload_pdf_to_s3,is_existing_object,generate_presigned_url_for_image
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
TTL_SECONDS = 60*60


def send_ocr_tasks_for_pdf(
    pdf_url: str,
    hash_: str,
    batches: list[list[int]],
    total_pages: int
) -> str:
    sigs = []
    for batch in batches:
        
        sig = celery_app.signature(
            "app.tasks.ocr.pdf",
            kwargs={"url": pdf_url, "hash": hash_,
                    "pages": batch, "total_pages": total_pages},
            options={"queue": "ocr"},
        )
        sigs.append(sig)
        
    group_result = group(sigs).apply_async()
    group_result.save()
    return group_result.id


def send_render_tasks_for_pdf(
    hash_: str,
    pdf_url: str,
    batches: list[int],
    zoom_x: float,
    zoom_y: float,
) -> str:
    sigs = []
    for batch in batches:
        sig = celery_app.signature(
            "app.tasks.render.pdf",
            kwargs={"hash_": hash_, "url": pdf_url, "page": batch, "zoom_x": zoom_x, "zoom_y": zoom_y},
            options={"queue": "render"},
        )
        sigs.append(sig)
        
    group_result = group(sigs).apply_async()
    group_result.save()
    return group_result.id

async def is_existing_objects(s3_client: Any, page_indexes: list[int], hash_: str, bucket: str | None = None, sem: asyncio.Semaphore | None = None) -> bool:

    bucket = bucket or os.getenv("AWS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME is not set")
    tasks=[]
    for page_index in page_indexes:
        object_key = f"{hash_}/images/page_{page_index}.png"
        tasks.append(is_existing_object(s3_client=s3_client, bucket=bucket, key=object_key, sem=sem))
    results=await asyncio.gather(*tasks)
    return all(results)

async def get_presigned_urls_for_images(s3_client: Any, page_indexes: list[int], hash_: str, bucket: str | None = None, sem: asyncio.Semaphore | None = None, expires_in: int = 60 * 60 * 24) -> dict:
    bucket = bucket or os.getenv("AWS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME is not set")
    tasks=[]
    for page_index in page_indexes:
        object_key = f"{hash_}/images/page_{page_index}.png"
        tasks.append(generate_presigned_url_for_image(s3_client=s3_client, bucket=bucket, key=object_key, semaphore=sem, expires_in=expires_in))
    urls=await asyncio.gather(*tasks)
    return {f"page_{page_index}": url for page_index, url in zip(page_indexes, urls)}


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
):

    if not file and not url:
        raise HTTPException(status_code=400, detail="You must provide either a file or a url.")
    if file and url:
        raise HTTPException(status_code=400, detail="Provide either file or url, not both.")

    s3_client = req.app.state.s3_client
    redis_client=req.app.state.redis_client
    semaphore = asyncio.Semaphore(max_concurrency)
   
    openai_client=req.app.state.openai_client
    pdf_bytes = (
        await load_pdf_bytes_from_url(app=req.app, file=file)
        if file
        else await load_pdf_bytes_from_url(app=req.app, url=url)
    )
    
    hash_sha1 = hashlib.sha256(pdf_bytes).hexdigest()[:12]
    document_key = f"doc:{hash_sha1}"
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
        
        batches=[list(range(i, min(i + pages_per_batch, total_pages + 1))) for i in range(1, total_pages + 1, pages_per_batch)]
        group_id_ocr=send_ocr_tasks_for_pdf(pdf_url=pdf_url, hash_=hash_sha1, batches=batches,total_pages=total_pages)
        return {"ocr_task": group_id_ocr,"hash": hash_sha1,"total_pages": total_pages}

    finally:
            logger.info(f"Closing document: {document_key}")
            doc.close()
    