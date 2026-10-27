import os
from celery import Celery
from dotenv import load_dotenv
import os
import pymupdf 
import pymupdf4llm
import logging
import redis

load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(os.getenv("REDIS_URL"))
logger.info(os.getenv("TESSDATA_PREFIX"))
logger.info(f"Pymupdf version: {pymupdf.__version__}")

logger.info(f"Pymupdf tessdata: {pymupdf.get_tessdata()}")
celery_app = Celery(
    "ocr_pipeline",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
    include=["app.tasks.ocr"], 
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_max_tasks_per_child=50,
    result_expires=3600,
    result_extended=True,
    task_routes={
      
        "app.tasks.ocr.pdf": {"queue": "ocr"},
     
    },
)



redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=False)
