import logging
from pathlib import Path
import json
import pytest
import asyncio
from app.urls import URLS
import time 

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

TEST_CASES = [
    # pytest.param(
    #     {
    #         "kind": "url",
    #         "value": "https://catalogue.ogsl.ca/data/zip-rne/ca-cioos_f10f496a-acf4-4274-9c7b-7a005bcf54ed/ziprne_portrait_ecogeomorphologique.pdf",
    #         "expected_status": 200,
    #     },
    #     id="from_url",
    # ),
        pytest.param(
            {
                "kind": "file",
                "value": "test_files/1155be503678.pdf",
                "expected_status": 200,
            },
            id="from_file",
        ),
    
]


@pytest.mark.parametrize("case", TEST_CASES)
@pytest.mark.asyncio
async def test_pdf_upload(client, case):
    data = {
        "start_page": "0",
        "max_concurrency": "2",
        "zoom_x": "2.0",
        "zoom_y": "2.0",
        "expires_in": "600",
        "pages_per_batch": "15",
    }
    files = None
    response = None
    group_id = None
     
    if case["kind"] == "url":
        data["url"] = case["value"]
        response = await client.post("/upload/pdf", data=data)
        
    else:
        test_path = Path(case["value"])
        assert test_path.exists(), f"Test PDF not found: {test_path}"

        with test_path.open("rb") as f:
            files = {"file": (test_path.name, f, "application/pdf")}
            response = await client.post("/upload/pdf", data=data, files=files)
           
    logger.info(f"Received response: {response.json()}")
    render_tasks=response.json().get("render_tasks")
    # assert response is not None, "No response received from the server"
    # assert response.status_code == case["expected_status"], f"Expected status {case['expected_status']}, got {response.status_code}: {response.text}"
    # assert response.json()["tasks"] is not None, "No tasks returned from the server"
    # group_id= response.json().get("tasks")
    # # group_id="bfad190f-00b2-49d3-837a-5f3de2def09e"
    # if group_id:
    #     start_time = time.time()
    #     while True:
    #         tasks_response=await client.get("/ocr_tasks/task_status?group_id="+group_id)
    #         assert tasks_response.status_code == 200
    #         tasks_data = tasks_response.json()
    #         all_finished = tasks_data.get("ready", False)
    #         if all_finished is True:
    #             logger.info(f"Group {group_id} finished.")
    #             end_time = time.time()
    #             logger.info(f"Total time taken: {end_time - start_time:.2f} seconds")
    #             break
    #         await asyncio.sleep(1)
    


    
    