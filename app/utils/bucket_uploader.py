import os
import aioboto3
import fitz
import pymupdf
from typing import Any, Generator, Iterable
import asyncio
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()
from urllib.parse import urlparse, urlunparse
import os
from collections.abc import Iterator
import pymupdf
import logging
logger = logging.getLogger(__name__)

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





# Assumes these already exist in your codebase:
# router, logger, BUCKET, UploadResponse, render_pages, upload_get_url

DEFAULT_CONCURRENCY = 10


# --------------------------------------------------------------------------
# Small pure helpers
# --------------------------------------------------------------------------
def dpi_to_zoom(dpi: float) -> float:
    """PDF user space is 72 units per inch."""
    return dpi / 72.0


def page_image_key(hash_: str, page: int) -> str:
    return f"{hash_}/images/page-{page}.png"


def get_page_count(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
async def load_pdf_bytes(redis_client: Any, hash_: str) -> bytes:
    pdf_bytes = await redis_client.hget(f"doc:{hash_}", "pdf_bytes")
    if not pdf_bytes:
        raise Exception(f"PDF not found in Redis for hash {hash_}. Please upload the PDF first.")
    return pdf_bytes


# --------------------------------------------------------------------------
# Rendering (CPU-bound -> run off the event loop)
# --------------------------------------------------------------------------
def _render_page_images_sync(
    pdf_bytes: bytes, pages: list[int], zoom: float
) -> list[tuple[int, bytes]]:
    images = render_pages(
        pdf_bytes, page_indexes=pages, zoom_x=zoom, zoom_y=zoom, img_type="png"
    )
    # strict=True raises if render_pages yields a different number of images
    # than pages requested, instead of silently dropping pages.
    return list(zip(pages, images, strict=True))


async def render_page_images(
    pdf_bytes: bytes, pages: list[int], dpi: float
) -> list[tuple[int, bytes]]:
    zoom = dpi_to_zoom(dpi)
    return await asyncio.to_thread(_render_page_images_sync, pdf_bytes, pages, zoom)


# --------------------------------------------------------------------------
# Uploading
# --------------------------------------------------------------------------
async def upload_page_image(
    s3_client: Any,
    bucket: str,
    hash_: str,
    page: int,
    data: bytes,
    semaphore: asyncio.Semaphore,
) -> dict[int, str | None]:
    try:
        return await upload_get_url(
            s3_client,
            bucket=bucket,
            key=page_image_key(hash_, page),
            data=data,
            content_type="image/png",
            semaphore=semaphore,
            page_number=page,
        )
    except Exception:
        logger.exception(f"Failed to upload page {page} for hash {hash_}")
        return {page: None}


async def upload_page_images(
    s3_client: Any,
    bucket: str,
    hash_: str,
    images: Iterable[tuple[int, bytes]],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[int, str]:
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(
        *(
            upload_page_image(s3_client, bucket, hash_, page, data, semaphore)
            for page, data in images
        )
    )
    return {k: v for r in results for k, v in r.items() if v is not None}


# --------------------------------------------------------------------------
# Orchestration (the "service" function the endpoint calls)
# --------------------------------------------------------------------------
async def render_and_upload_pages(
    pdf_bytes: bytes,
    hash_: str,
    pages: list[int],
    dpi: float,
    s3_client: Any,
    bucket: str,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[int, str]:
    logger.info(f"Rendering {len(pages)} pages for hash {hash_} at {dpi} DPI")
    images = await render_page_images(pdf_bytes, pages, dpi)

    urls = await upload_page_images(s3_client, bucket, hash_, images, concurrency)
    logger.info(f"Uploaded {len(urls)}/{len(pages)} pages for hash {hash_}")
    return urls


async def upload_all_pages(
    pdf_bytes: bytes,
    hash_: str,
    s3_client: Any,
    bucket: str,
    dpi: float = 72,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[int, str]:
    """Render and upload every page; returns {page_number: presigned_url}."""
    total = get_page_count(pdf_bytes)
    # Use the same page numbering convention that render_pages expects.
    pages = list(range(1, total + 1))
    return await render_and_upload_pages(
        pdf_bytes, hash_, pages, dpi, s3_client, bucket, concurrency
    )


async def upload_pdf_bytes_from_s3(
    s3_client: Any, bucket: str, hash_: str, semaphore: asyncio.Semaphore
) -> bytes:
    """Download the PDF bytes from S3 and return them."""
    object_key = f"{hash_}/pdf/{hash_}.pdf"
    async with semaphore:
        response = await s3_client.get_object(Bucket=bucket, Key=object_key)
        pdf_bytes = await response["Body"].read()
    return pdf_bytes