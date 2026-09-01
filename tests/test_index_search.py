
import logging
from pathlib import Path
import json
import pytest
import asyncio
from app.utils.text_utils import page_windows,flatten_to_spans,index_spans,get_text,index_documents,index_spans

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_opensearch_insert(app,client):
  task_id="ec0e5439-9256-4d67-b59c-0efd436f2dfe"
  response = await client.get(f"/ocr_tasks/task_status?group_id={task_id}")
  
  assert response.status_code == 200
  status = response.json()
  
  if status['ready'] ==True and status['tasks'][0]['name']=="app.tasks.ocr.pdf":
   

    doc_hash=status['tasks'][0]['result']['hash']
    logger.info(f"Task hash: {doc_hash}")
    
    tasks=[task['result']['layout'] for task in status['tasks'] if task['result'] is not None]
    flattened_tasks = [item for sublist in tasks for item in sublist]
    

    windows = page_windows(flattened_tasks)
    windows_data=[]
    for w in windows:
      
        text=" ".join(get_text(p) for p in w)
        page_numbers="_".join(str(p["page_number"]) for p in w)
        d={
        "doc_hash": doc_hash, 
        "text": text,
        "page_numbers": page_numbers,
        "page_start": w[0]["page_number"], 
        "page_end": w[-1]["page_number"]}
        windows_data.append(d)
    
    opensearch_client = app.state.opensearch_client
    success, errors = await index_documents(opensearch_client, windows_data, doc_hash)
    logger.info(f"Indexing document success: {success}, errors: {errors}")
  
    await opensearch_client.indices.refresh(index="page_windows")  # add this
    success, errors = await index_spans(opensearch_client, flattened_tasks, doc_hash)
    logger.info(f"Indexing spans success: {success}, errors: {errors}")
    await opensearch_client.indices.refresh(index="spans")  # add this