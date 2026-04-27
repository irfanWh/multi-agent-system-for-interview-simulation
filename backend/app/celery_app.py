import os
from celery import Celery

# Get Redis URLs from environment variables
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "interviewai",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.tasks.resume",
        "app.tasks.evaluate",
        "app.tasks.report",
    ]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour
    task_default_queue="default",
)

if __name__ == "__main__":
    celery_app.start()
