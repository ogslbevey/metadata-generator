
import pytest
import asyncio
import logging
from app.utils.mlflow_utils import build_traces_organized_eov

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_extract(client):
    text = (
        "A station to collect CTD data (Station B) was done for JHC in order to "
        "calibrate the multibeam sonar system. The MVP is being worked on and "
        "should be available within a day or two."
    )
    payload = {
        "model": [
        {
            "provider": "openai",
            "model": "gpt-5-mini",
            
        },
        # {
        #     "provider": "openai",
        #     "model": "gpt-5-mini",
        # }
        
        ],
        "text": text,
        "hash": "test_hash",
        "source": "test_source",
    }

    response = await client.post("/extract/eov", json=payload)

    assert response.status_code == 200, response.text   # shows the error body if it fails
    body = response.json()
    assert "results" in body
    assert "run_id" in body
    run_id = body["run_id"]
    return run_id, body["results"]


    
