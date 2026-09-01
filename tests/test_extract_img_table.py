import pytest
import asyncio
import logging

@pytest.mark.asyncio
async def test_extract_table(client):
    image_s3_prefix = "1155be503678/page-190.png"  # Replace with an actual S3 prefix for testing
    payload = {"s3_prefix": image_s3_prefix}
    response = await client.post(f"/extract/img/table", json=payload)
    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response JSON: {response.json()}")
    assert response.status_code == 200