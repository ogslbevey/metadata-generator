import logging
from typing import Any, Iterable, Iterator

from opensearchpy.helpers import async_bulk
from opensearchpy import AsyncOpenSearch
logger = logging.getLogger(__name__)

SPANS_INDEX = "spans"


SPANS_MAPPING = {
    "mappings": {
        "properties": {
            "doc_hash": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "box_index": {"type": "integer"},
            "line_index": {"type": "integer"},
            "span_index": {"type": "integer"},
            "boxclass": {"type": "keyword"},
            "text": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
            "x0": {"type": "float"}, "y0": {"type": "float"},
            "x1": {"type": "float"}, "y1": {"type": "float"}
          
        }
    }
}

PAGE_WINDOWS_INDEX = "documents"

DOCUMENT_MAPPING = {

    "mappings": {
        "properties": {
            "doc_hash": {"type": "keyword"},
            "page_numbers": {"type": "integer"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "page_width": {"type": "float"},
            "page_height": {"type": "float"},
            "text": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
        }
    }
}

#Excluded boxclasses for searching in the document.
EXCLUDED_BOXCLASSES = {"picture", "page-header", "page-footer", "table"}

async def ensure_spans_index(client) -> None:
    """Create the index with an explicit mapping (call once at startup)."""
    if not await client.indices.exists(index=SPANS_INDEX):
        await client.indices.create(index=SPANS_INDEX, body=SPANS_MAPPING)


async def ensure_documents_index(client) -> None:
    """Create the index with an explicit mapping (call once at startup)."""
    if not await client.indices.exists(index=PAGE_WINDOWS_INDEX):
        await client.indices.create(index=PAGE_WINDOWS_INDEX, body=DOCUMENT_MAPPING)

async def delete_spans(client: AsyncOpenSearch, doc_hash: str) -> int:
    """Delete all spans belonging to doc_hash. Returns number deleted."""
    if not await client.indices.exists(index=SPANS_INDEX):
        return 0

    resp = await client.delete_by_query(
        index=SPANS_INDEX,
        body={"query": {"term": {"doc_hash": doc_hash}}},
        conflicts="proceed",   # don't abort if a doc changed mid-delete
        refresh=True,          # make the deletion visible immediately
    )
    deleted = resp.get("deleted", 0)
    if deleted:
        logger.info("Deleted %d existing spans for %s", deleted, doc_hash)
    return deleted



def flatten_to_spans(
    data: dict[str,dict],
    doc_hash: str,
    source: str = "layout",
    exclude: set[str] = EXCLUDED_BOXCLASSES,
) -> tuple[list[dict], dict[str, str]]:
    """Return (spans, page_text).

    spans:     one doc per span, plus one doc per box with no text.
    page_text: {"1": "text...", ...} excluding boxes in `exclude`.
    """

   
    
    all_spans: list[dict] = []
    page_text: dict[str, list[str]] = {}
    page_sizes: dict[str, tuple[float, float]] = {}
    for page in data.values():
        page_number = page["page_number"]
        page_width = page.get("width")
        page_height = page.get("height")
        page_text.setdefault(str(page_number), [])     # page present even if empty

        for box_idx, box in enumerate(page.get("boxes") or []):
            boxclass = box.get("boxclass")
            box_bbox = [box.get("x0"), box.get("y0"), box.get("x1"), box.get("y1")]
            include_text = boxclass not in exclude
            emitted = 0

            for line_idx, line in enumerate(box.get("textlines") or []):
                for span_idx, span in enumerate(line.get("spans") or []):
                    text = span.get("text") or ""
                    if not text.strip():
                        continue

                    all_spans.append({
                        "_id": f"{doc_hash}_{page_number}_{box_idx}_{line_idx}_{span_idx}",
                        "doc_hash": doc_hash,
                        "page_number": page_number,
                      
                        "boxclass": boxclass,
                        "box_idx": box_idx,
                        "line_idx": line_idx,
                        "span_idx": span_idx,
                        "block": span.get("block"),
                        "text": text,
                        "bbox": span.get("bbox") or box_bbox,
                        "has_text": True,
                    })
                    emitted += 1
                    page_sizes[str(page_number)] = (page_width, page_height)

                    if include_text:
                        page_text[str(page_number)].append(text)

            if emitted == 0:
                all_spans.append({
                    "_id": f"{doc_hash}_{page_number}_{box_idx}_box",
                    "doc_hash": doc_hash,
                    "page_number": page_number,
                    "boxclass": boxclass,
                    "box_idx": box_idx,
                    "line_idx": None,
                    "span_idx": None,
                    "block": None,
                    "text": None,
                    "bbox": box_bbox,
                    "has_text": False,
                })

    joined = {p: " ".join(parts).strip() for p, parts in page_text.items()}
    return all_spans, joined, page_sizes



async def index_spans(
    client: AsyncOpenSearch,
    data:list[dict],
    doc_hash: str,
    chunk_size: int = 500,
) -> tuple[int, list[Any]]:
    """Bulk-index every span of `pages`. Returns (success_count, errors)."""
    
    logger.info(f"Indexing spans for {doc_hash}...")
    await delete_spans(client, doc_hash)
    actions = (
    {
        "_index": SPANS_INDEX,
        "_id": s["_id"],
        "_source": {k: v for k, v in s.items() if k != "_id"},
    }
    for s in data
    )

    success, errors = await async_bulk(
        client, actions, chunk_size=chunk_size, raise_on_error=False
    )
    if errors:
        logger.warning("Span indexing for %s: %d errors, first: %s",  len(errors), errors[0])
    return success, errors


async def index_documents(
    client: AsyncOpenSearch,
    windows_data: list[dict],
    doc_hash: str,
    chunk_size: int = 500,  
) -> tuple[int, list[Any]]:
    """Bulk-index every page window. Returns (success_count, errors)."""
    if not windows_data:
        return 0, []

   
    logger.info(f"Indexing page windows for {doc_hash}...")
    await ensure_documents_index(client)  # ensure index exists before indexing

    actions = (
    {
        "_index": PAGE_WINDOWS_INDEX,
        "_id": w["_id"],
        "_source": {k: v for k, v in w.items() if k != "_id"},
    }
    for w in windows_data
    )

    success, errors = await async_bulk(
        client, actions, chunk_size=chunk_size, raise_on_error=False
    )
    if errors:
        logger.warning("Page window indexing for %s: %d errors, first: %s",  len(errors), errors[0])
    return success, errors



def create_page_windows(
    page_text: dict[str, str],
    page_sizes: dict[str, tuple[float, float]],
    doc_hash: str,
    window_size: int = 2,
    stride: int = 1,
) -> list[dict]:
    """Create overlapping multi-page windows: 1-2, 2-3, 3-4, ... (for window_size=2, stride=1)."""
    pages = sorted(int(p) for p in page_text)     # numeric sort: 2 before 10
    if not pages:
        return []

    # A document shorter than the window still gets one window covering all its pages
    last_start = max(len(pages) - window_size, 0)
    windows = []

    for i in range(0, last_start + 1, stride):
        group = pages[i : i + window_size]
        start, end = group[0], group[-1]
        sizes = [page_sizes.get(str(p), (None, None)) for p in group]

        windows.append({
            "_id": f"{doc_hash}_{start}_{end}",
            "doc_hash": doc_hash,
            "page_numbers": group,
            "page_start": start,
            "page_end": end,
            "page_widths": [w for w, _ in sizes],
            "page_heights": [h for _, h in sizes],
            "text": "\n\n".join(t for p in group if (t := page_text[str(p)])),
        })

    return windows
