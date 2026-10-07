import asyncio
import logging
import time
import json
from typing import Any

from celery.result import GroupResult
from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter
from app.utils.opensearch_utils.index import index_documents, index_spans, flatten_to_spans, create_page_windows
from app.tasks import celery_app
logger = logging.getLogger(__name__)

KEEP_ALIVE_SECONDS = 15
POLL_SECONDS = 1
router = APIRouter(prefix="/ocr_tasks", tags=["ocr_tasks"])


def _sse(
    event: str,
    data: Any,
    event_id: str | None = None,
    retry_ms: int | None = None,
) -> str:
    """Format one Server-Sent Event.

    A message is a block of "field: value" lines ending with a blank line.
    json.dumps with no indent always produces a single line (newlines inside
    strings are escaped), so the payload fits in one "data:" field.
    """
    lines: list[str] = []

    if event_id is not None:
        # Newlines would end the field early and corrupt the stream
        lines.append(f"id: {str(event_id).replace(chr(10), '').replace(chr(13), '')}")
    if retry_ms is not None:
        lines.append(f"retry: {int(retry_ms)}")

    lines.append(f"event: {event}")
    lines.append(
        "data: "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    )

    return "\n".join(lines) + "\n\n"
def _read_result(task):
    """Blocking result-backend calls, run in a thread."""
    return task.successful(), task.result


async def _index_document(client, pages_data: dict[int, dict], doc_hash: str) -> None:
    all_spans, joined, page_sizes = flatten_to_spans(pages_data, doc_hash)
    await index_spans(client, all_spans, doc_hash)
    page_windows = create_page_windows(joined, page_sizes, doc_hash)
    await index_documents(client, page_windows, doc_hash)

def _pages_from_result(result: dict) -> dict[int, dict]:
    """Return {page_number: page} from a task result's layout."""
    layout = result.get("layout")
    if isinstance(layout, str):  # some tasks return the layout as a JSON string
        try:
            layout = json.loads(layout)
        except json.JSONDecodeError:
            logger.warning("Task layout is not valid JSON")
            return {}

    pages = layout.get("pages", layout) if isinstance(layout, dict) else layout
    out: dict[int, dict] = {}

    if isinstance(pages, list):
        first = int(result.get("start_page", 1))
        for i, page in enumerate(pages):
            if isinstance(page, dict):
                out[int(page.get("page_number") or first + i)] = page
    elif isinstance(pages, dict):
        for k, v in pages.items():
            if str(k).isdigit() and isinstance(v, dict):
                out[int(k)] = v

    if not out:
        logger.warning("No pages in task result. result keys=%s, layout type=%s",
                       list(result.keys()), type(layout).__name__)
    return out


@router.get("/task_status")
async def get_group_status(req: Request, group_id: str):
    gr = await asyncio.to_thread(GroupResult.restore, group_id, app=celery_app)

    async def event_generator():
        # Always answer with SSE so the browser's EventSource can read it
        if gr is None:
            yield _sse("not_found", {"group_id": group_id})
            return

        total = len(gr.results)
        sent: set[str] = set()
        pages_data: dict[int, dict] = {}
        doc_hash: str | None = None
        last_ping = time.monotonic()

        yield _sse("start", {"group_id": group_id, "total": total})

        while len(sent) < total:
            if await req.is_disconnected():
                return

            for task in gr.results:
                if task.id in sent:
                    continue
                if not await asyncio.to_thread(task.ready):
                    continue

                sent.add(task.id)
                ok, result = await asyncio.to_thread(_read_result, task)

                if ok and isinstance(result, dict) and "layout" in result:
                    doc_hash = doc_hash or result.get("hash")
                    task_pages = _pages_from_result(result)
                    pages_data.update(task_pages)
                    yield _sse("task", {
                        "task_id": task.id,
                        "pages": task_pages,
                        "completed": len(sent),
                        "total": total,
                        "hash": doc_hash,
                    }, event_id=task.id)
                else:
                    yield _sse("task_error", {
                        "task_id": task.id,
                        "error": str(result),
                        "completed": len(sent),
                        "total": total,
                    }, event_id=task.id)

            if len(sent) < total:
                if time.monotonic() - last_ping >= KEEP_ALIVE_SECONDS:
                    yield ": keep-alive\n\n"
                    last_ping = time.monotonic()
                await asyncio.sleep(POLL_SECONDS)

        index_error = None
        if doc_hash is not None:
            try:
                await _index_document(req.app.state.opensearch_client, pages_data, doc_hash)
            except Exception as e:  # report it instead of killing the stream silently
                logger.exception("Indexing failed for %s", doc_hash)
                index_error = str(e)

        # Pages were already sent one task at a time, so they are not repeated here
        yield _sse("complete", {
            "group_id": group_id,
            "total": total,
            "hash": doc_hash,
            "indexed": doc_hash is not None and index_error is None,
            "error": index_error,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )