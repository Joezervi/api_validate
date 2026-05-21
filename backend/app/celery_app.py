from celery import Celery
from app.config import REDIS_URL

celery = Celery(
    "tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)
