from app.celery_app import celery_app
import logging
import httpx
import pymupdf
import fitz
import io
import pymupdf4llm
import json
import copy

logger = logging.getLogger(__name__)

boxes_to_choose=["text","section-header","table","caption"]
keys_to_remove = [
    "size",
    "flags",
    "bidi",
    "char_flags",
    "font",
    "color",
    "alpha",
    "ascender",
    "descender",
    "origin",
    "dir",
    "line"
]

@celery_app.task(
    bind=True,
    name="app.tasks.ocr.pdf",
)
def get_pdf_layout(self, url: str) -> dict:
    doc=None
    try:
        response = httpx.get(url, timeout=60,follow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        md = pymupdf4llm.to_json(
                doc,
                header=False,
                footer=False,
                ocr_language="eng+fra",
                force_ocr=True
            )
        layout = json.loads(md)
        pages = layout.get("pages", []) or []
        pages_cleaned = copy.deepcopy(pages)
        text=""
        for page in pages_cleaned:
            fulltext=page.pop("fulltext",None)
            words=page.pop("words",None)
            links=page.pop("links",None)

            for box in page.get("boxes",[]) or []:
                box.pop("x0",None)
                box.pop("y0",None)
                box.pop("x1",None)
                box.pop("y1",None)
                table=box.get("table",None)
                if table is not None:
                    # table.pop("cells",None)
                    table.pop("markdown",None)
                    # table.pop("bbox",None)
                    
                for textline in box.get("textlines",[]) or []:
                    textline.pop("bbox",None)
                    
                    for span in textline.get("spans",[]) or []:
                        for key in keys_to_remove:
                            span.pop(key,None)
                        
         

        return {
            "url": url,
            "status": "success",
            "result": pages_cleaned
        }

    except httpx.HTTPError as e:
        logger.error(f"Error fetching image from {url}: {e}")
        return {
            "url": url,
            "status": "failed",
            "error": str(e)
        }
    finally:
        if doc:
            doc.close()
    