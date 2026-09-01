import os

from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request

# from img2table.ocr import TesseractOCR
# from img2table.document import Image
# from io import BytesIO
from dotenv import load_dotenv
# import pytesseract
from PIL import Image
import io

load_dotenv()
bucket = os.getenv("AWS_BUCKET_NAME")

# ocr = TesseractOCR(n_threads=5, lang="eng")

async def download_image_from_s3(s3_client, key) -> bytes:
    bucket=os.getenv("AWS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_BUCKET_NAME environment variable is not set")
    response = await s3_client.get_object(Bucket=bucket, Key=key)
    return await response["Body"].read()

# def extract_table_from_image(image_bytes: bytes) -> str:
#     doc= Image(BytesIO(image_bytes))
#     extracted_tables = doc.extract_tables(ocr=ocr,
#                                       implicit_rows=False,
#                                       implicit_columns=False,
#                                       borderless_tables=False,
#                                       min_confidence=20)
    
#     tables=[]
#     for table in extracted_tables:
#         d={'capt': table.title, 'data': table.df.to_dict(orient='split'), 'bbox': table.bbox}
#         tables.append(d)
#     return tables


# def extract_tessaract_text(image_bytes: bytes) -> str:
#     image = Image.open(io.BytesIO(image_bytes))
#     text = pytesseract.image_to_string(image)
#     return text.strip()


# if __name__ == "__main__":
#     import asyncio
#     from app.utils.bucket_uploader import download_image_from_s3, extract_table_from_image
#     from app.utils.parser import load_pdf_bytes_from_url
#     import httpx

#     async def main():
        
#         async with httpx.AsyncClient() as client:
#             image_bytes = await download_image_from_s3(client, bucket, "1a2b3c4d/page-1.png")
#             table_md = extract_table_from_image(image_bytes)
#             print(table_md)

#     asyncio.run(main())
