import pytest
import asyncio
import logging
logger = logging.getLogger(__name__)



@pytest.mark.asyncio
async def test_extract_from_mlflow(app, client):
    run_id = "57fa17f70ed8487fa31a4e502dc3621a"  # Replace with a valid run_id
    response = await client.get(f"/mlflow/mlflow/{run_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "type" in body
    assert "results" in body
    logger.info(f"MLflow results for run_id {run_id}: {body}")