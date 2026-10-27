
import pytest
import logging
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_models(client):
    response=await client.get("/models/")
    assert response.status_code == 200, response.text
    logger.info(f"Models response: {response.json()}")