"""Celery application configuration"""

from celery import Celery
from config import get_settings

settings = get_settings()

# Создаем Celery app
celery_app = Celery(
    'aismm_scraping',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['tasks.scraping_tasks']
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут максимум на задачу
    task_soft_time_limit=25 * 60,  # 25 минут софт лимит
    worker_prefetch_multiplier=1,  # По одной задаче на воркер
    task_acks_late=True,  # Подтверждать задачи после выполнения
    task_reject_on_worker_lost=True,
)

if __name__ == '__main__':
    celery_app.start()
