from fastapi import APIRouter, Request, UploadFile, File, Form,Request
from app.tasks import celery_app
from pydantic import BaseModel
import logging
from celery.result import GroupResult
from app.utils.text_utils import page_windows,flatten_to_spans,index_spans,get_text,index_documents,index_spans


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr_tasks", tags=["ocr_tasks"])

async def doc_already_indexed(client, doc_hash: str) -> bool:
    resp = await client.count(
        index="page_windows",
        body={"query": {"term": {"doc_hash": doc_hash}}}
    )
    return resp["count"] > 0

async def delete_doc_from_index(client, doc_hash: str):
    for index in ("page_windows", "spans"):
        await client.delete_by_query(
            index=index,
            body={"query": {"term": {"doc_hash": doc_hash}}},
            refresh=True  # blocks until deletion visible
        )
    logger.info(f"Deleted existing data for {doc_hash}")
    
@router.get("/task_status")
async def get_group_status(req: Request, group_id: str):
    """Get the status of a group of tasks."""
    redis_client = req.app.state.redis_client
    gr = GroupResult.restore(group_id, app=celery_app)
    if gr is None:
        return {"group_id": group_id, "status": "NOT_FOUND_OR_EXPIRED"}
    
    if gr.ready() == True:
        task_name = gr.results[0].name
        if task_name == "app.tasks.ocr.pdf":
            doc_hash = gr.results[0].result['hash']
            logger.info(f"Group {group_id} is ready. Task name: {task_name} Hash: {doc_hash}")
            
            opensearch_client = req.app.state.opensearch_client

            # # ✅ Check first — skip all work if already indexed
            # count = await opensearch_client.count(
            #     index="page_windows",
            #     body={"query": {"term": {"doc_hash": doc_hash}}}
            # )
            # if count["count"] > 0:
            #     logger.info(f"Document {doc_hash} already indexed, skipping.")
            # else:
            tasks = [r.result['layout'] for r in gr.results if r.successful() and r.result is not None]
            flattened_tasks = [item for sublist in tasks for item in sublist]
            logger.info(f"Flattened tasks: {len(flattened_tasks)}")
            
            windows = page_windows(flattened_tasks)
            windows_data = []
            for w in windows:
                text = " ".join(get_text(p) for p in w)
                page_numbers = "_".join(str(p["page_number"]) for p in w)
                d = {
                    "doc_hash": doc_hash,
                    "text": text,
                    "page_numbers": page_numbers,
                    "page_start": w[0]["page_number"],
                    "page_end": w[-1]["page_number"]
                }
                windows_data.append(d)

            success, errors = await index_documents(opensearch_client, windows_data, doc_hash)
            logger.info(f"Indexing document success: {success}, errors: {errors}")
            await opensearch_client.indices.refresh(index="page_windows")
            success, errors = await index_spans(opensearch_client, flattened_tasks, doc_hash)
            logger.info(f"Indexing spans success: {success}, errors: {errors}")
            await opensearch_client.indices.refresh(index="spans")

    return {
        "group_id": group_id,
        "total": len(gr),
        "completed": gr.completed_count(),
        "ready": gr.ready(),
        "successful": gr.successful(),
        "failed": gr.failed(),
        "tasks": [
            {
                "task_id": r.id,
                "status": r.status,
                "result": r.result if r.successful() else None,
                "name": r.name,
            }
            for r in gr.results
        ],
    }