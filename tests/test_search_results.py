import pytest
import logging


logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_text_search(client):
    
    query="""Compiled by André Rochon
    Table of content"""
    doc_hash="dd6153a13e17"
    results=await client.get("/search/",params={"query":query,"document_hash":doc_hash})
    logger.info(f"Search results: {results.json()}")


@pytest.mark.asyncio
async def test_pages_with_image(client):
    doc_hash="dd6153a13e17"
    results=await client.get("/search/pages_with_image",params={"document_hash":doc_hash})
    logger.info(f"Search results: {results.json()}")