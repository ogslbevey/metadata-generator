from dotenv import load_dotenv
import os
from app.core.context import Resources, with_resources
import asyncio 
from dotenv import load_dotenv
import aioboto3
from botocore.config import Config
import logging
logger=logging.getLogger(__name__)
load_dotenv()


# # GET /page_windows/_search
# # {
# #   "query": {
# #     "bool": {
# #       "must": [
# #         { "term": { "doc_hash": "1155be503678"} }
       
# #       ]
# #     }
# #   }
# # }


# GET /page_windows/_search
# {
#   "query": {
#     "bool": {
#       "must": [
#         { "term": { "doc_hash": "1155be503678"} },
#         { "match_phrase": {
#             "text": {
#               "query": "Les données de salinité montrent des valeurs fluctuantes entre 0,2 et 30,0 PSU (Annexe III). Ces données indiquent des milieux d’eau douce (salinité inférieure à 1 g/L), saumâtre (salinité comprise entre 1 et 10 g/L) et d’eau salée (salinité au-delà de 10g/L). Les données ont été collectées à marée basse."
              
#             }
#         }}
#       ]
#     }
#   },
#   "highlight": { "fields": { "text": {} } },
#   "size": 2
# }


# GET /spans/_search
# {
#   "size": 100,
#   "query": {
#     "bool": {
#       "filter": [
#         { "term":  { "doc_hash":"1155be503678" } },
#         { "terms":  { "page_number": [77,78,79] } },
#         { "terms": { "boxclass": ["text", "section-header","caption"] } }
#       ],
#       "must": [
#         { "match": {
#             "text": { "query": "Tableau 17. Espèces de poissons capturés dans le marais du secteur de la BMV en 2019 et en 2021.", "minimum_should_match": "1" }
#         }}
#       ]
#     }
#   },
#   "sort": [
#     { "block":  "asc" },
#     { "box_idx": "asc" },
#     {"line_idx": "asc"},
#     { "span_idx": "asc" }
#   ]
# }
@with_resources
async def upload_file(key: str, *, resources: Resources) -> None:
    BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
    if not BUCKET_NAME:
        logger.error("AWS_BUCKET_NAME is not set in environment variables.")
        return
    s3 = resources.s3_client
   
    data=b"Hello, this is a test file for S3 upload!"
    await s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=data)
    await asyncio.sleep(1)  # wait for eventual consistency
    resp = await s3.get_object(Bucket=BUCKET_NAME, Key=key)
    body = await resp["Body"].read()
    print(f"Uploaded and verified S3 object: {body.decode()}")
    
    
@with_resources
async def redis_test(resources: Resources) -> None:
    redis = resources.redis_client
    await redis.set("test_key", "Hello, Redis!")
    value = await redis.get("test_key")
    print(f"Redis test key value: {value}")
@with_resources
async def opensearch_test(resources: Resources) -> None:
    opensearch = resources.opensearch_client
    index_name = "test-index"
    doc_id = "1"
    document = {"title": "Test Document", "content": "This is a test document for OpenSearch."}
    
    # Index the document
    await opensearch.index(index=index_name, id=doc_id, document=document)
    
    # Retrieve the document
    response = await opensearch.get(index=index_name, id=doc_id)
    print(f"OpenSearch retrieved document: {response['_source']}")
if __name__ == "__main__":
    upload_file("test-file.txt")
    