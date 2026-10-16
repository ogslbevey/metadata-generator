import pytest
import asyncio
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
@pytest.mark.asyncio
async def test_extract_table(client,app):
    payload={
        "hash": "dd6153a13e17",
        "pages": [1,2,3,4,5],
        "dpi": 150

    }
  
    response = await client.post("/upload/image", json=payload)