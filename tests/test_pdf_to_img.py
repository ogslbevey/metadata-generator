
import json
import logging
import os

import pytest

import asyncio

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_pdf_to_image(client):
    payload = {
        "hash": "dd6153a13e17",
        "pages": [200],
        "model": {
            "provider": "openai",
            "model": "gpt-4.1",
            "temperature": 0.1
    
        }
    }
    response = await client.post("/extract/table", json=payload)
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response body: {response.text}")
    logger.info(f"Response JSON: {response.json()}")
    assert response.status_code == 200
    
    logger.info(f"Extracted tables: {response.json()}")