import os
from celery import Celery
from dotenv import load_dotenv
import os


load_dotenv()

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
    task_routes={
      
        "app.tasks.ocr.*": {"queue": "ocr"},
    },
)



