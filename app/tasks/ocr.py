from app.celery_app import celery_app
import logging
import httpx
import pymupdf
import fitz
import io
import pymupdf4llm
import json
import copy
import asyncio 
from img2table.ocr import TesseractOCR
from img2table.document import Image
from io import BytesIO
import pandas as pd
from img2table.ocr import TesseractOCR
from img2table.ocr._types import OCRData
from img2table.document._types import Document, MockDocument


class SafeTesseractOCR(TesseractOCR):
    """img2table 2.0.0 can emit word records with value=None (junk text that
    survives the confidence filter). Those crash _group_words_by_parent's
    ' '.join(...). Strip them here before they reach text extraction."""

    def of(self, document: Document | MockDocument) -> OCRData | None:
        data = super().of(document=document)
        if data is None:
            return None
        for page, words in data.records.items():
            data.records[page] = [w for w in words if w.get("value") is not None]
        return data


ocr = SafeTesseractOCR(n_threads=20, lang="eng+fra")
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

def get_text(batch: list[dict]) -> str:
    d={}

    for page in batch:
    
        text=""
        boxes=page.get("boxes",[])
        for box in boxes:
            if box.get('boxclass') in ["text","section-header","caption","title"]:
                textlines=box.get("textlines",[])
                for textline in textlines:
                    for span in textline.get("spans",[]):
                        text+=span.get("text","") + " "
        d[page.get("page_number")]=text.strip()
    return d

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
            "status": "SUCCESS",
            "result": pages_cleaned,
            "type": "pymudf4llm",
        }

    except httpx.HTTPError as e:
        logger.error(f"Error fetching image from {url}: {e}")
        return {
            "url": url,
            "status": "FAILED",
            "error": str(e)
        }
    finally:
        if doc:
            doc.close()
            


def extract_table_from_image(image_bytes: bytes, page_number: int) -> list[dict]:
    doc = Image(BytesIO(image_bytes))
    extracted_tables = doc.extract_tables(
        ocr=ocr,
        implicit_rows=False,
        implicit_columns=False,
        borderless_tables=False,
        min_confidence=50,
    )

    tables = []

    for table in extracted_tables:
        try:
            df = table.df.replace({float("nan"): None})
            df = df.where(pd.notnull(df), None)

            data = df.to_dict(orient="split")

            tables.append({
                "page_number": page_number,
                "capt": table.title,
                "data": data,
                "bbox": [
                    table.bbox.x1,
                    table.bbox.y1,
                    table.bbox.x2,
                    table.bbox.y2,
                ],
            })
        except Exception as e:
            logger.error(f"Error converting table to DataFrame: {e}")
            continue

    return tables

async def fetch_image(client:httpx.AsyncClient, item: dict, semaphore:asyncio.Semaphore) -> dict:

    url = item["url"]
    async with semaphore:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            image_bytes = response.content
            table_md = extract_table_from_image(image_bytes, item.get("page_number"))
           
            return {
                "type":"img2table",
                "status": "SUCCESS",
                "result": {"url": url, "page_number": item.get("page_number"), "tables": table_md} # Placeholder for actual table data
                
               
            }
        except httpx.HTTPError as e:
            logger.error(f"Error fetching image from {url}: {e}")
            return {
                "url": url,
                "page_number": item.get("page_number"),
                "status": "FAILED",
                "error": str(e)
            }
        
async def process_images(batch: list[dict]) -> list[dict]:
   

    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [
            fetch_image(client, item, semaphore)
            for item in batch
        ]

        return await asyncio.gather(*tasks)

@celery_app.task(
    bind=True,
    name="app.tasks.ocr.image",
)
def get_image_layout(self, batch: list[dict]) -> list[dict]:
    return asyncio.run(process_images(batch))

    




