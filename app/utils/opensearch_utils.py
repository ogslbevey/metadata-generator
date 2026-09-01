from opensearchpy import AsyncOpenSearch
import logging
from difflib import SequenceMatcher
from app.utils.text_utils import preprocess_text
logger = logging.getLogger(__name__)




# Finds the best results and possible two pages that contain the query
async def search_windows(
    client: AsyncOpenSearch,
    doc_hash: str,
    query: str,
    size: int = 1
  
):
    body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_hash": doc_hash}}
                ],
                "should": [
                    {
                        "match_phrase": {
                            "text": {
                                "query": query,
                                "slop": 3
                               
                            }
                        }
                    },
                   
                ],
                
            }
        },
        "highlight": {"fields": {"text": {}}},
        "size": size,
        "_source": ["doc_hash", "page_numbers", "page_start", "page_end"],
    }

    response = await client.search(index="page_windows", body=body)
    hits = response['hits']['hits']
    if not hits:
        return []

    return hits

# Finds the best spans that contain the query by measuring sequential match in the given pages as a result of the search_windows function
async def search_spans(
    client: AsyncOpenSearch,
    doc_hash: str,
    query: str,
    page_numbers: list[int],
    size: int = 100
):
    body = {
        "size": size,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"doc_hash": doc_hash}},
                    {"terms": {"page_number": page_numbers}},  # <-- terms for a list
                    {"terms": {"boxclass": ["text", "section-header", "caption"]}}
                ],
                "must": [
                    {"match": {
                        "text": {
                            "query": query,
                            "minimum_should_match": "1"
                        }
                    }}
                ]
            }
        },
        "sort": [
            {"page_number": "asc"},
            {"block": "asc"},
            {"box_idx": "asc"},
            {"line_idx": "asc"},
            {"span_idx": "asc"}
        ]
    }

    response = await client.search(index="spans", body=body)
    return response["hits"]["hits"]

 

def reconstruct_query_spans(query: str, hits: list[dict]) -> list[dict]:
    spans = sorted(
        hits,
        key=lambda h: (
            h["_source"]["page_number"],
            h["_source"]["block"],
            h["_source"]["box_idx"],
            h["_source"]["line_idx"],
        ),
    )

    norm_query = preprocess_text(query)
    norm_texts = [preprocess_text(s["_source"]["text"]) for s in spans]
    query_tokens = set(norm_query.split())

    best = None  # (score, start, end)

    for i in range(len(spans)):
        # only start a window if the first span has token overlap with the query
        first_span_tokens = set(norm_texts[i].split())
        overlap = first_span_tokens & query_tokens
        if not overlap:
            continue  # skip — no point starting here

        combined = ""
        for j in range(i, len(spans)):
            combined = (combined + " " + norm_texts[j]).strip()
            score = SequenceMatcher(None, combined, norm_query).ratio()
            if best is None or score > best[0]:
                best = (score, i, j)
            if len(combined) > len(norm_query) * 1.5:
                break

    if best is None:
        return []  # no overlapping span found at all

    _, start, end = best
    return spans[start : end + 1]