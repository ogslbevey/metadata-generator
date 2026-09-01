from fastapi import APIRouter, UploadFile, File, HTTPException,Form, Depends, Request
import logging 
import json
from pydantic import BaseModel
from difflib import SequenceMatcher
from app.utils.text_utils import preprocess_text
from app.utils.opensearch_utils import search_windows,search_spans,reconstruct_query_spans
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    document_hash: str | None = None
    window_size: int = 2

async def search(client: any, doc_hash: str, query: str):
    results = await search_windows(client, doc_hash=doc_hash, query=query)
    if not results:
        return {"similarity": 0.0, "spans": []}
    
    pages = [results[0]["_source"]["page_start"], results[0]["_source"]["page_end"]]
    searched_spans = await search_spans(client, doc_hash=doc_hash, query=query, page_numbers=pages)
    reconstructed_spans = reconstruct_query_spans(query, searched_spans)
    all_texts = " ".join(span["_source"]["text"] for span in reconstructed_spans)
    
    similarity = SequenceMatcher(None, preprocess_text(all_texts), preprocess_text(query)).ratio()
    logger.info(f"Similarity: {similarity}")
    return {"similarity": similarity, "spans": reconstructed_spans,"text": all_texts}

@router.get("/")
async def search_endpoint(request: Request, search_request: SearchRequest = Depends()):
    q = search_request.query
    doc_hash = search_request.document_hash
    window_size = search_request.window_size
    logger.info(f"Received search request: query='{q}', document_hash='{doc_hash}', window_size={window_size}")
    opensearch_client = request.app.state.opensearch_client
    search_response = await search(opensearch_client, doc_hash=doc_hash, query=q)
    return search_response
   
    





