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
ocr = TesseractOCR(n_threads=12, lang="eng+fra")
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
            


def extract_table_from_image(image_bytes: bytes,page_number: int) -> str:
    doc= Image(BytesIO(image_bytes))
    extracted_tables = doc.extract_tables(ocr=ocr,
                                      implicit_rows=False,
                                      implicit_columns=False,
                                      borderless_tables=False,
                                      min_confidence=20)
    
    tables=[]
    for table in extracted_tables:
        try:
            data=table.df.to_dict(orient='split')
            tables.append({
                'page_number': page_number,
                'capt': table.title,
                'data': data,
                'bbox': [table.bbox.x1, table.bbox.y1, table.bbox.x2, table.bbox.y2]
                })
        except Exception as e:
            logger.error(f"Error converting table to DataFrame: {e}")
            continue
        
    return tables    

async def fetch_image(client:httpx.AsyncClient, item: dict, semaphore:asyncio.Semaphore) -> dict:
    logger.info(item)
    url = item["url"]
    async with semaphore:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            image_bytes = response.content
            
            pymupdf4llm.to_json(fitz.open("pdf", image_bytes), header=False, footer=False, ocr_language="eng+fra", force_ocr=True)
            
            # table_md = extract_table_from_image(image_bytes, item.get("page_number"))
           
            return {
                "url": url,
                "page_number": item.get("page_number"),
                "status": "success",
                "result": table_md
                
               
            }
        except httpx.HTTPError as e:
            logger.error(f"Error fetching image from {url}: {e}")
            return {
                "url": url,
                "page_number": item.get("page_number"),
                "status": "failed",
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

urls=['https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-183.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=2TVViM9hd6yeUxwPCdpnBElev0Y%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-184.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=x1m8cjj1v5p1BsGyagkH%2FDzKXSY%3D&Expires=1779330022', 
'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-185.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=FBqHPWGGc3IxipN9fvoo2y%2BkbRo%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-186.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=%2BRicY4coBWjS23%2BFmQggXY1Px7I%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-187.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=M6krC9XleW73BhnhncZL3%2BExfcQ%3D&Expires=1779330022', 
'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-188.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=g%2F2jS%2BrTLPu5STGJV7aGh0T0p%2FQ%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-189.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=m9wfuqvlqdF4PWH3580SGm3edNw%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-190.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=IgJCz5BZfhlcnnhCUfwo4ck0JQ8%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-191.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=iYfvXigmxK6uiR3LPcqMCDzJyJ8%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-192.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=mD3PJk%2B7aVGNPmEz0C7uun%2Fuhao%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-193.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=IDXH9ZlWngyDKrU0FyCqYKD3Iu0%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-194.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=Ryc7a%2BJ7i9LRW3GranfPsyqrz4c%3D&Expires=1779330022', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-195.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=XY%2FTPa%2BI%2FreQSIytffwID1QgBrE%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-196.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=kweIBfcz101ioM%2B%2Fezldv3r4LQk%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-197.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=FTIm7Q5pqQWgGnujZMjvQ8ZmwWY%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-198.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=LynEA6poTRQYf588ebwZVto0yys%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-199.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=aXitqSg7FNyRxWqieutaeZpyQ4k%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-200.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=j3jbxyXkxDnJOlfmL8zAVJzUZEM%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-201.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=PwVY4cynnC9%2Bq%2BbIOiBYkfRZ2hY%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-202.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=1SAHfaI7PuzWU1OZvAgOCzVqZVE%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-203.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=weZS%2Buc9UCUVCGsR9x93ZJSMGcI%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-204.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=BScEtSDzT5XXXfoLlaAcagSxkE0%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-205.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=pcT%2B7l96o2i0GRln6mpINoThQGY%3D&Expires=1779330023', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-206.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=1C48FpXU66zEYLmKoy2RVfq7ARg%3D&Expires=1779330024', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-207.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=su6SLBVrITFb1YOeWE%2BmoydyB6g%3D&Expires=1779330024', 'https://bucket-production-f88a.up.railway.app/observia/1155be503678/images/page-208.png?AWSAccessKeyId=zt0QkmWa4T1OiId9YVqE&Signature=JjenC60Ft2UNQaRR6vCcIOtdcUw%3D&Expires=1779330024']

if __name__ == "__main__":
    test_url = "https://observia-ocr-results.s3.eu-west-3.amazonaws.com/1687827378_1c9e5b9c-1a7b-4c8e-9cbd-2f0d0a7cbbac.pdf"
    result = get_pdf_layout(test_url)
    print(json.dumps(result, indent=2))
    




