# from img2table.ocr import TesseractOCR
# from img2table.ocr._types import OCRData
# from img2table.document._types import Document, MockDocument


# class SafeTesseractOCR(TesseractOCR):
#     """img2table 2.0.0 can emit word records with value=None (junk text that
#     survives the confidence filter). Those crash _group_words_by_parent's
#     ' '.join(...). Strip them here before they reach text extraction."""

#     def of(self, document: Document | MockDocument) -> OCRData | None:
#         data = super().of(document=document)
#         if data is None:
#             return None
#         for page, words in data.records.items():
#             data.records[page] = [w for w in words if w.get("value") is not None]
#         return data


# ocr = SafeTesseractOCR(n_threads=20, lang="eng+fra")



# def extract_table_from_image(image_bytes: bytes, page_number: int) -> list[dict]:
#     doc = Image(BytesIO(image_bytes))
#     extracted_tables = doc.extract_tables(
#         ocr=ocr,
#         implicit_rows=False,
#         implicit_columns=False,
#         borderless_tables=False,
#         min_confidence=50,
#     )

#     tables = []

#     for table in extracted_tables:
#         try:
#             df = table.df.replace({float("nan"): None})
#             df = df.where(pd.notnull(df), None)

#             data = df.to_dict(orient="split")

#             tables.append({
#                 "page_number": page_number,
#                 "capt": table.title,
#                 "data": data,
#                 "bbox": [
#                     table.bbox.x1,
#                     table.bbox.y1,
#                     table.bbox.x2,
#                     table.bbox.y2,
#                 ],
#             })
#         except Exception as e:
#             logger.error(f"Error converting table to DataFrame: {e}")
#             continue

#     return tables

# async def fetch_image(client:httpx.AsyncClient, item: dict, semaphore:asyncio.Semaphore) -> dict:

#     url = item["url"]
#     async with semaphore:
#         try:
#             response = await client.get(url, follow_redirects=True)
#             response.raise_for_status()
#             image_bytes = response.content
#             table_md = extract_table_from_image(image_bytes, item.get("page_number"))
           
#             return {
#                 "type":"img2table",
#                 "status": "SUCCESS",
#                 "result": {"url": url, "page_number": item.get("page_number"), "tables": table_md} # Placeholder for actual table data
                
               
#             }
#         except httpx.HTTPError as e:
#             logger.error(f"Error fetching image from {url}: {e}")
#             return {
#                 "url": url,
#                 "page_number": item.get("page_number"),
#                 "status": "FAILED",
#                 "error": str(e)
#             }
        
# async def process_images(batch: list[dict]) -> list[dict]:
   

#     semaphore = asyncio.Semaphore(5)

#     async with httpx.AsyncClient(timeout=60) as client:
#         tasks = [
#             fetch_image(client, item, semaphore)
#             for item in batch
#         ]

#         return await asyncio.gather(*tasks)

# @celery_app.task(
#     bind=True,
#     name="app.tasks.ocr.image",
# )
# def get_image_layout(self, batch: list[dict]) -> list[dict]:
#     return asyncio.run(process_images(batch))

# def get_text(batch: list[dict]) -> str:
#     d={}
#     for page in batch:
    
#         text=""
#         boxes=page.get("boxes",[])
#         for box in boxes:
#             if box.get('boxclass') in ["text","section-header","caption","title"]:
#                 textlines=box.get("textlines",[])
#                 for textline in textlines:
#                     for span in textline.get("spans",[]):
#                         text+=span.get("text","") + " "
#         d[page.get("page_number")]=text.strip()
#     return d