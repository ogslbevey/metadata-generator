import re
import unicodedata

import re
import logging 
from app.urls import URLS
from app.core.context import Resources,with_resources
from app.utils.mlflow_utils import build_traces_organized
import asyncio
import fitz
from opensearchpy.helpers import async_bulk

logger= logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

units=["km","m","cm","mm","kg","g","mg","l","ml","s","ms","h","min"]

def flatten_to_spans(pages: list[dict], hash: str):
    """Yield one flat span document per span across all pages."""
    for page in pages:
        page_number = page["page_number"]
        width = page["width"]
        height = page["height"]

        for box_idx, box in enumerate(page["boxes"]):
            boxclass = box.get("boxclass")
            textlines = box.get("textlines") or []  # ← guard against None/missing

            for line_idx, line in enumerate(textlines):
                spans = line.get("spans") or []      # ← guard against None/missing

                for span_idx, span in enumerate(spans):
                    text = span.get("text")
                    if not text:                      # ← skip empty/None spans
                        continue

                    yield {
                        "_id": f"{hash}_{page_number}_{box_idx}_{line_idx}_{span_idx}",
                        "doc_hash": hash,
                        "page_number": page_number,
                        "width": width,
                        "height": height,
                        "boxclass": boxclass,
                        "box_idx": box_idx,
                        "line_idx": line_idx,
                        "span_idx": span_idx,
                        "block": span.get("block"),
                        "text": text,
                        "bbox": span.get("bbox"),     # ← .get() instead of []
                    }

async def index_spans(client, pages: list[dict], hash: str):
    actions = (
        {
            "_index": "spans",
            "_id": span["_id"],
            "_source": {k: v for k, v in span.items() if k != "_id"},
        }
        for span in flatten_to_spans(pages, hash)
    )
    success, errors = await async_bulk(
        client,
        actions,
        refresh=False,
        raise_on_error=False,
        chunk_size=500,
    )
    return success, errors
    
def clean_text(text: str) -> str:
    # collapse any run of whitespace (incl. the voids from joins) to one space
    text = re.sub(r"\s+", " ", text)
    # remove space after an apostrophe: "l' azote" -> "l'azote"
    text = re.sub(r"([’'])\s+", r"\1", text)
    # remove space before punctuation: "ammoniacal ," -> "ammoniacal,"
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()

def get_text(page: dict) -> str:
    text = ""
    boxes = page.get("boxes", [])
    for box in boxes:
        if box.get('boxclass') in ["text","section-header","caption","title"]:
            textlines = box.get("textlines", [])
            for textline in textlines:
                for span in textline.get("spans", []):
                    text += span.get("text", "") + " "
    return text.strip()
        
async def index_windows(client, windows: list[dict]):
    actions = (
        {
            "_index": "page_windows",
            "_id": w["_id"],
            "_source": {k: v for k, v in w.items() if k != "_id"},
        }
        for w in windows
    )
    success, errors = await async_bulk(
        client, actions, refresh=False, raise_on_error=False, chunk_size=500
    )
    return success, errors
    
def page_windows(pages: list[dict], size: int = 2, step: int = 1):
    pages = sorted(pages, key=lambda p: p["page_number"])
    
    for i in range(0, len(pages) - size + 1, step):
        
        yield pages[i : i + size]




def preprocess_text(text: str) -> str:
    # 1. remove accents
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text=text.lower()
    # 2. normalize spaces
    text = re.sub(r"\s+", " ", text)

    # 3. build unit pattern dynamically
    unit_pattern = "|".join(map(re.escape, units))

    # 4. match:
    #    - km [2]
    #    - g/m [2]
    #    - kg/m [2]
    pattern = rf"\b((?:{unit_pattern})(?:/(?:{unit_pattern}))?)\s*\[\s*(\d+)\s*\]"

    # 5. replace → unit2
    text = re.sub(pattern, r"\1\2", text)

    # 6. clean slashes spacing
    text = re.sub(r"\s*/\s*", "/", text)
    # remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)

    # normalize spaces
    text = re.sub(r"\s+", " ", text)
    return text

async def index_spans(client, pages: list[dict], hash: str):
    actions = (
        {
            "_index": "spans",
            "_id": span["_id"],
            "_source": {k: v for k, v in span.items() if k != "_id"},
        }
        for span in flatten_to_spans(pages, hash)
    )
    success, errors = await async_bulk(
        client,
        actions,
        refresh=False,
        raise_on_error=False,
        chunk_size=500,
    )
    return success, errors




async def index_documents(client, documents: list[dict], hash: str):
    actions = (
        {
            "_index": "page_windows",
            "_id": f"{hash}_{doc.get('page_numbers')}",
            "_source": doc, 
        }
        for doc in documents
    )
    success, errors = await async_bulk(
        client,
        actions,
        refresh=False,
        raise_on_error=False,
        chunk_size=100,
    )
    return success, errors


