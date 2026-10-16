import pytest
import asyncio
import logging
logger = logging.getLogger(__name__)



@pytest.mark.asyncio
async def test_extract_from_mlflow(app, client):
    run_id = "b4e9a79568674a2ab5a7c7a755c2b09f"  # Replace with a valid run_id
    response = await client.get(f"/mlflow/mlflow/{run_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "type" in body
    assert "results" in body
    logger.info(f"MLflow results for run_id {run_id}: {body['results']}")
    result=body["results"]
    assert isinstance(result, dict)
    assert "columns" in result
    assert "data" in result
    assert isinstance(result["columns"], list)
    assert isinstance(result["data"], list)