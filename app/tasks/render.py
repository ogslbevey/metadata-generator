
import fitz
import logging
from app.celery_app import celery_app
from app.tasks.cache import get_pdf_bytes

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="app.tasks.render.pdf",
)
def render_pdf(self,hash_: str, url: str, page: int, zoom_x: float=2.0, zoom_y: float=2.0) -> dict:
    pages_decrement = page - 1
    doc = None
    try:
        pdf_bytes = get_pdf_bytes(hash_,url)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
       
        page_obj = doc.load_page(pages_decrement)
        mat = fitz.Matrix(zoom_x, zoom_y)
        pix = page_obj.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes(output="png")
        return {
            "status": "SUCCESS",
            "type": "render",
            "hash": hash_,
            "page": page,
            "image_bytes": img_bytes,
        }
    except Exception as e:
        logger.error(f"Error rendering PDF page {page}: {e}")
        raise
    finally:
        if doc:
            doc.close() 