import logging
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL")
logger = logging.getLogger(__name__)
logger.info(f"REDIS_URL: {REDIS_URL} in CELERY_APP")
celery_app = Celery(
    "fastapi_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
