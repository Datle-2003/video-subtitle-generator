import os
from celery import Celery
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "video_subtitle",
    broker=REDIS_URL, # define message queue
    backend=REDIS_URL, # define place to store task results
    include=["app.tasks.celery_worker"]
)

celery_app.conf.update(
    task_serializer="json",  
    accept_content=["json"], 
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True
)
