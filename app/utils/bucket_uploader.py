import os
import aioboto3
import fitz
import pymupdf
from typing import Any
import asyncio
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()
from urllib.parse import urlparse, urlunparse
import os


async def is_existing_object(s3_client: Any, bucket: str, key: str,sem: asyncio.Semaphore) -> bool:
    try:
        async with sem:
            await s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        else:
            raise
            
async def upload_pdf_to_s3(
    s3_client: Any,
    pdf_bytes: bytes,
    hash_: str,
    bucket: str | None = None,
    TTL_SECONDS: int = 60 * 60 * 24
) -> str:
    bucket = bucket or os.getenv("AWS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME is not set")

    object_key = f"{hash_}/pdf/{hash_}.pdf"
    try:
        await s3_client.head_object(Bucket=bucket, Key=object_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code in {"404", "NoSuchKey", "NotFound"}:
            await s3_client.put_object(Bucket=bucket, Key=object_key, Body=pdf_bytes, ContentType="application/pdf")
        else:
            raise

    presigned_url = await s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
        },
        ExpiresIn=TTL_SECONDS,
    )

    return {
        "key": object_key,
        "url": presigned_url,
    }

async def generate_presigned_url_for_image(s3_client: Any, bucket: str, key: str, semaphore: asyncio.Semaphore, expires_in: int = 60 * 60 * 24) -> str:
    async with semaphore:
        presigned_url = await s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
    return presigned_url

def render_page_to_png(pdf_bytes: bytes, page_index: int, zoom_x: float, zoom_y: float) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pdf_page = doc.load_page(page_index)
        mat = pymupdf.Matrix(zoom_x, zoom_y)
        pix = pdf_page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        return png_bytes
    finally:
        doc.close()

async def render_and_upload(
    *,
    s3_client: Any,
    pdf_bytes:bytes,
    page: dict,
    hash_: str,
    sem: asyncio.Semaphore,
    zoom_x: float,
    zoom_y: float,
    expires_in: int = 60 * 60 * 24,
    bucket: str | None = None,
) -> dict:
    bucket = bucket or os.getenv("AWS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME is not set")
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        async with sem:
            page_number = page["page"]          # 1-based for API output
            page_index = page_number - 1        # 0-based for fitz
            object_key = f"{hash_}/images/page-{page_number}.png"

            try:
                await s3_client.head_object(Bucket=bucket, Key=object_key)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")

                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    pdf_page = doc.load_page(page_index)
                    mat = pymupdf.Matrix(zoom_x, zoom_y)
                    pix = pdf_page.get_pixmap(matrix=mat)
                    png_bytes = pix.tobytes("png")

                    await s3_client.put_object(
                        Bucket=bucket,
                        Key=object_key,
                        Body=png_bytes,
                        ContentType="image/png",
                    )
                else:
                    raise

            presigned_url = await s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": object_key,
                },
                ExpiresIn=expires_in,
            )

            return {
                "page_number": page_number,
                "key": object_key,
                "url": presigned_url,
                }
                
            
    finally:
        doc.close()


