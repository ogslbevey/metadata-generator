import gc
import json
import logging
import pymupdf
import pymupdf4llm

from app.celery_app import celery_app
from app.tasks.cache import get_pdf_bytes

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.ocr.pdf")
def get_pdf_layout(self, url: str, hash: str, pages: list,
                   total_pages: int, ocr: bool = False) -> dict:
    page_indexes = [page - 1 for page in pages]
    doc = None
    try:
        pdf_bytes = get_pdf_bytes(hash, url)
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

        return {
            "url": url,
            "status": "SUCCESS",
            "type": "pymupdf4llm",
            "hash": hash,
            "layout": layout_pages,
        }

    except Exception:
        logger.exception("Error processing PDF %s", url)
        raise

    finally:
        if doc is not None:
            doc.close()
        pymupdf.TOOLS.store_shrink(100)  # empty MuPDF's internal cache
        gc.collect()