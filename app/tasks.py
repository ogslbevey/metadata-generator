import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "fastapi_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
