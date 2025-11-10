# Продолжение реализации T6: Асинхронная система скрапинга

## ✅ Что уже сделано

### 1. База данных и модели
- ✅ Таблица `posts` с полной спецификацией T6
- ✅ Обновлена таблица `sources` (handle, is_private, post_count, status, meta)
- ✅ Создана модель `ScrapingJob` для отслеживания асинхронных задач
- ✅ Миграции 003 и 004 готовы (004 еще не применена!)

### 2. Схемы (schemas.py)
- ✅ `SourceVerifyRequest/Response` по T6 spec
- ✅ `SourceCreateV2Request/Response`
- ✅ `ScrapeRequest/Response` с job_id
- ✅ `JobStatusResponse` для отслеживания прогресса
- ✅ `ManualPostsRequest/Response`
- ✅ `HintsRequest/Response`

### 3. Инфраструктура скрапинга
- ✅ Архитектура scrapers (BaseScraper, TelegramScraper, VKScraper, InstagramScraper)
- ✅ ScraperFactory для автоопределения платформы
- ✅ ScrapingService для оркестрации

### 4. Middleware
- ✅ RateLimitMiddleware (30 req/min)
- ✅ IdempotencyMiddleware
- ✅ AuthMiddleware

### 5. Celery
- ✅ celery[redis] добавлен в requirements.txt
- ✅ celery_app.py с конфигурацией
- ✅ Папка api/tasks/ создана

### 6. Тестирование
- ✅ Проверка источников работает
- ✅ Сбор 100 постов протестирован
- ✅ Данные в БД корректны
- ✅ Rate limiting работает
- ✅ Idempotency работает

---

## 🎯 Что нужно сделать дальше

### Приоритет 1: Celery Tasks (КРИТИЧНО)

Создать файл `api/tasks/scraping_tasks.py`:

```python
from celery import Task
from celery_app import celery_app
from datetime import datetime
import uuid

@celery_app.task(bind=True, name='scraping.run_scraping_job')
def run_scraping_job(self, job_id: str, user_id: str, source_ids: list = None):
    """
    Асинхронная задача для скрапинга контента

    1. Обновить статус джобы на 'running'
    2. Получить источники для скрапинга
    3. Для каждого источника:
       - Запустить соответствующий scraper
       - Сохранить посты
       - Обновить прогресс в ScrapingJob
    4. Установить статус 'done' или 'partial'
    """
    # TODO: Полная реализация
    pass
```

### Приоритет 2: Обновление эндпоинтов

#### 2.1 POST /sources/verify
Обновить под новую схему:
```python
# Текущая схема: SourceVerifyRequest(url, user_id)
# Новая схема: SourceVerifyRequest(platform, url)
# Response: {handle, accessible, private, post_count, normalized_url, message}
```

#### 2.2 POST /sources
Добавить новый эндпоинт с v2 схемой:
```python
@router.post("/sources/v2", response_model=SourceCreateV2Response)
async def create_source_v2(...):
    # Использует SourceCreateV2
    # Возвращает {source_id, status: "verified"}
```

#### 2.3 POST /ingest/scrape
Переделать на асинхронный:
```python
@router.post("/ingest/scrape")
async def scrape_source(...):
    # 1. Создать ScrapingJob в БД
    # 2. Запустить Celery task: run_scraping_job.delay(...)
    # 3. Вернуть {job_id, status: "queued", message}
```

#### 2.4 GET /ingest/status
Новый эндпоинт:
```python
@router.get("/ingest/status")
async def get_job_status(job_id: UUID, db: AsyncSession = Depends(get_db)):
    # Найти ScrapingJob по ID
    # Вернуть JobStatusResponse
```

#### 2.5 POST /ingest/manual_posts
Новый эндпоинт:
```python
@router.post("/ingest/manual_posts")
async def add_manual_posts(data: ManualPostsRequest, ...):
    # Создать посты с platform="manual"
    # Вернуть {stored: count}
```

#### 2.6 POST /ingest/hints (опционально)
```python
@router.post("/ingest/hints")
async def add_hints(data: HintsRequest, ...):
    # Сохранить референсные источники
    # Вернуть {status, references_added, message}
```

### Приоритет 3: Docker Compose

Обновить `infra/docker-compose.yml`:

```yaml
# Добавить Celery worker
celery-worker:
  build:
    context: ../api
    dockerfile: Dockerfile
  container_name: aismm-celery-worker
  command: celery -A celery_app worker --loglevel=info
  env_file:
    - ../.env
  environment:
    - POSTGRES_HOST=postgres
    - REDIS_URL=redis://redis:6379/0
  volumes:
    - ../api:/app
  depends_on:
    - postgres
    - redis
    - api
  networks:
    - aismm-network

# Опционально: Flower для мониторинга
flower:
  build:
    context: ../api
    dockerfile: Dockerfile
  container_name: aismm-flower
  command: celery -A celery_app flower --port=5555
  ports:
    - "5555:5555"
  environment:
    - REDIS_URL=redis://redis:6379/0
  depends_on:
    - redis
    - celery-worker
  networks:
    - aismm-network
```

### Приоритет 4: Применить миграцию

```bash
cd infra
docker-compose exec api bash -c "cd /migrations && alembic upgrade head"
```

Должна создаться таблица `scraping_jobs`.

### Приоритет 5: Тестирование

1. Запустить Celery worker
2. Создать джобу через POST /ingest/scrape
3. Проверить статус через GET /ingest/status
4. Убедиться что посты собираются асинхронно
5. Проверить manual posts
6. Проверить hints (опционально)

---

## 📁 Структура файлов

```
api/
├── celery_app.py          ✅ Создан
├── tasks/
│   ├── __init__.py        ✅ Создан
│   └── scraping_tasks.py  ❌ НУЖНО СОЗДАТЬ
├── scrapers/              ✅ Готово
├── services/
│   └── scraping_service.py ✅ Готово
├── middleware/            ✅ Готово
├── routers/
│   ├── auth.py            ✅ Готово
│   └── onboarding.py      ⚠️ НУЖНО ОБНОВИТЬ
├── models.py              ✅ ScrapingJob добавлен
├── schemas.py             ✅ Все схемы готовы
└── requirements.txt       ✅ Celery добавлен

migrations/versions/
├── 003_*.py               ✅ Применена
└── 004_add_scraping_jobs.py ❌ НУЖНО ПРИМЕНИТЬ
```

---

## 🚀 Quick Start для следующей сессии

```bash
# 1. Получить последние изменения
cd ~/AI-SMM
git pull

# 2. Перезапустить контейнеры
cd infra
docker-compose down
docker-compose up -d --build

# 3. Применить миграцию 004
docker-compose exec api bash -c "cd /migrations && alembic upgrade head"

# 4. Проверить что все работает
docker-compose logs api | tail -20
docker-compose logs celery-worker | tail -20  # После добавления в docker-compose

# 5. Начать разработку
# - Создать api/tasks/scraping_tasks.py
# - Обновить api/routers/onboarding.py
# - Добавить Celery в docker-compose.yml
```

---

## 📊 Прогресс: 60% ✅

- [x] Модели и миграции
- [x] Схемы данных
- [x] Инфраструктура скрапинга
- [x] Middleware
- [x] Celery конфигурация
- [ ] Celery tasks (20%)
- [ ] Эндпоинты (30%)
- [ ] Docker compose (10%)
- [ ] Тестирование (0%)

---

## 💡 Важные заметки

1. **Mock данные**: Все scrapers сейчас возвращают mock данные. Это нормально для T6.
2. **Redis уже есть**: В docker-compose уже настроен Redis - он будет broker для Celery
3. **Qdrant point_id**: Поле есть в posts, но интеграция с Qdrant - отдельная задача
4. **Старые эндпоинты**: Можно оставить `/sources/verify` и `/ingest/scrape` как legacy, добавив `/v2` версии

---

## 🎯 Цель следующей сессии

**Получить полностью рабочую асинхронную систему скрапинга по спецификации T6!**

Ожидаемый результат:
- ✅ POST /ingest/scrape создает джобу и возвращает job_id
- ✅ Celery worker выполняет скрапинг в фоне
- ✅ GET /ingest/status показывает прогресс
- ✅ POST /ingest/manual_posts работает для ручного ввода
- ✅ Все протестировано через Swagger UI

**Удачи! 🚀**
