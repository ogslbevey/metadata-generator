import re
import pytest
import asyncio
import logging
from difflib  import SequenceMatcher
from app.utils.text_utils import preprocess_text
from app.utils.opensearch_utils import search_spans,search_windows,reconstruct_query_spans
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_text_search(client):

    query="""L’érosion que subissent les berges de la rivière du Moulin à Baude est 
    un phénomène naturel ayant pour conséquence d’accroître 
    la turbidité des eaux de surface (voir photo 3)."""
    doc_hash="e3531518ab7a"
    response = await client.get(
        "/search/",
        params={"query": query, "document_hash": doc_hash}
    )
    assert response.status_code == 200
    data = response.json()
    reconstructed_spans, similary = data
    assert isinstance(reconstructed_spans, list)
    assert similary > 0.5  # Adjust threshold as needed