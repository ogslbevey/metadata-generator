import os
import aioboto3
import fitz
import pymupdf
from typing import Any, Generator
import asyncio
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()
from urllib.parse import urlparse, urlunparse
import os
from collections.abc import Iterator
import pymupdf

SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "pnm", "pgm", "ppm", "pbm", "pam", "psd", "ps"}

def render_pages(
    pdf_bytes: bytes,
    page_indexes: list[int],
    zoom_x: float = 2.0,
    zoom_y: float = 2.0,
    img_type: str = "png",
) -> Iterator[bytes]:
    img_type = img_type.lower()
    if img_type not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image type: {img_type}")
    return _render(pdf_bytes, page_indexes, zoom_x, zoom_y, img_type)


def _render(pdf_bytes, page_indexes, zoom_x, zoom_y, img_type) -> Iterator[bytes]:
    mat = pymupdf.Matrix(zoom_x, zoom_y)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_index in page_indexes:
            try:
                pix = doc.load_page(page_index-1).get_pixmap(matrix=mat)
                yield pix.tobytes(img_type)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to render page {page_index + 1} to {img_type.upper()}: {e}"
                ) from e

async def is_existing_object(s3_client: Any, bucket: str, key: str,sem: asyncio.Semaphore) -> bool:
    try:
        async with sem:
            await s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False,key
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

async def upload_get_url(s3_client: Any, bucket: str, key: str, data: bytes, content_type: str, semaphore: asyncio.Semaphore, page_number: int, expires_in: int = 60 * 60 * 24) -> str:
    async with semaphore:
        await s3_client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        presigned_url = await s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
    return { str(page_number):presigned_url}




