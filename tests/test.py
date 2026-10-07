
import json
import logging
import os
from fastapi.responses import StreamingResponse
import pytest

import asyncio
from app.utils.opensearch_utils.index import index_documents, index_spans, index_spans,flatten_to_spans,create_page_windows
logger = logging.getLogger(__name__)

PDF_PATH = r"C:\Users\gulec\Downloads\Example2.pdf"
async def read_sse(client, url: str, params: dict, timeout: float = 300):
    """Collect (event, data) pairs from an SSE endpoint until 'complete'."""
    events: list[tuple[str, dict]] = []
    event_name = "message"

    async with client.stream("GET", url, params=params, timeout=timeout) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        async for line in resp.aiter_lines():
            if not line or line.startswith(":"):  # separator or keep-alive
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((event_name, json.loads(line.split(":", 1)[1])))
                if event_name == "complete":
                    break
                event_name = "message"

    return events




@pytest.mark.asyncio
async def test_upload(app, client):
    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    response = await client.post(
        "/upload/pdf",
        files={"file": ("Example2.pdf", pdf_bytes, "application/pdf")},
        data={"start_page": "1", "end_page": "3"},
    )
    assert response.status_code == 200
    group_id = response.json()["ocr_task"]
    async with client.stream("GET", url="/ocr_tasks/task_status", params={"group_id": group_id}, timeout=300) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
    
            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):  # separator or keep-alive
                    continue
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    logger.info(f"Received event: {event_name}")
                    data = json.loads(line.split(":", 1)[1])
                    logger.info(f"Data: {data['pages'].keys()}")
    
