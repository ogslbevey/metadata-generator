
import fitz
import logging
from app.celery_app import celery_app
from app.tasks.cache import get_pdf_bytes
from app.celery_app import s3_client
import os
logger = logging.getLogger(__name__)


def write_image_to_s3(bucket_name: str, key: str, image_bytes: bytes) -> None:
    try:
        s3_client.put_object(Bucket=bucket_name, Key=key, Body=image_bytes)
        url=s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=3600
        )
        return url
    except Exception as e:
        logger.error(f"Failed to upload image to S3: {e}")
        raise

@celery_app.task(
    bind=True,
    name="app.tasks.render.pdf",
)
def render_pdf(self,hash_: str, url: str, page: int, zoom_x: float=2.0, zoom_y: float=2.0) -> dict:
    BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
    if not BUCKET_NAME:
        logger.error("AWS_BUCKET_NAME environment variable is not set.")
        raise ValueError("AWS_BUCKET_NAME environment variable is required.")
    pages_decrement = page - 1
    doc = None
    try:
        pdf_bytes = get_pdf_bytes(hash_,url)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
       
        page_obj = doc.load_page(pages_decrement)
        mat = fitz.Matrix(zoom_x, zoom_y)
        pix = page_obj.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes(output="png")
        url = write_image_to_s3(BUCKET_NAME, f"{hash_}/images/{page}.png", img_bytes)
        return {
            "status": "SUCCESS",
            "type": "render",
            "hash": hash_,
            "page": page,
            "url": url
        }
    except Exception as e:
        logger.error(f"Error rendering PDF page {page}: {e}")
        raise
    finally:
        if doc:
            doc.close() 