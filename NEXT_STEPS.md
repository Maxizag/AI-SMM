# AI-SMM: Next Steps Guide

## ✅ Что полностью реализовано (T6 Complete!)

### 1. Асинхронная система скрапинга
- ✅ Celery worker с Redis в качестве broker
- ✅ Flower UI для мониторинга задач (http://localhost:5555)
- ✅ Модель `ScrapingJob` для отслеживания прогресса
- ✅ Асинхронная задача `scraping.run_scraping_job`

### 2. T6 API Endpoints (все работают!)
- ✅ POST /sources/verify - проверка источника по T6 spec
- ✅ POST /sources/v2 - создание проверенного источника
- ✅ POST /ingest/scrape - запуск асинхронного скрапинга
- ✅ GET /ingest/status - отслеживание прогресса задачи
- ✅ POST /ingest/manual_posts - ручной ввод постов
- ✅ POST /ingest/hints - добавление референсных источников

### 3. Инфраструктура
- ✅ Docker Compose с 11 контейнерами
- ✅ Celery worker с concurrency=2
- ✅ Flower для мониторинга
- ✅ Миграция 004 создает таблицу scraping_jobs
- ✅ Redis downgraded до 4.6.0 (совместимость с Celery 5.3.4)

### 4. База данных
- ✅ Таблица `posts` с полной T6 спецификацией
- ✅ Таблица `sources` с новыми полями (handle, is_private, post_count, status, meta)
- ✅ Таблица `scraping_jobs` для async tracking
- ✅ Все индексы и foreign keys настроены

### 5. Middleware & Auth
- ✅ RateLimitMiddleware (30 req/min)
- ✅ IdempotencyMiddleware
- ✅ AuthMiddleware
- ✅ Bearer token authentication работает

---

## 🎯 Следующие шаги (T7+)

### Приоритет 1: Реальный скрапинг (вместо mock данных)

Сейчас все scrapers возвращают mock данные. Для продакшена нужно:

#### Telegram
```bash
# 1. Зарегистрировать приложение на my.telegram.org
# 2. Получить API_ID и API_HASH
# 3. Добавить в .env:
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 4. Установить telethon
pip install telethon

# 5. Обновить TelegramScraper в api/scrapers/telegram.py
```

#### VK
```bash
# 1. Создать VK приложение на vk.com/dev
# 2. Получить ACCESS_TOKEN
# 3. Добавить в .env:
VK_ACCESS_TOKEN=your_token

# 4. Установить vk_api
pip install vk_api

# 5. Обновить VKScraper в api/scrapers/vk.py
```

#### Instagram
```bash
# 1. Создать Facebook/Instagram App
# 2. Получить access token
# 3. Добавить в .env:
INSTAGRAM_ACCESS_TOKEN=your_token

# 4. Установить instagrapi
pip install instagrapi

# 5. Обновить InstagramScraper в api/scrapers/instagram.py
```

### Приоритет 2: Интеграция с Qdrant

Сейчас `qdrant_point_id` в таблице `posts` всегда NULL.

**Задачи:**
1. Создать сервис для генерации embeddings (OpenAI embeddings API)
2. Сохранять векторы постов в Qdrant
3. Обновлять `qdrant_point_id` после сохранения в Qdrant
4. Создать эндпоинт для семантического поиска по постам

**Файлы для создания:**
- `api/services/embedding_service.py` - генерация embeddings
- `api/services/qdrant_service.py` - работа с Qdrant
- `api/tasks/embedding_tasks.py` - Celery task для векторизации

### Приоритет 3: Language Detection

Сейчас `lang` в таблице `posts` всегда NULL.

**Решение:**
```bash
# 1. Установить langdetect
pip install langdetect

# 2. Добавить в _save_posts() в scraping_service.py:
from langdetect import detect
lang = detect(post_data['text']) if post_data.get('text') else None
```

### Приоритет 4: Style Analysis

После накопления постов нужно:
1. Создать модель StyleProfile по постам пользователя
2. Анализ тона, частоты, тем, структуры постов
3. ML модель для генерации контента в стиле пользователя

**Файлы для создания:**
- `api/services/style_analyzer.py` - анализ стиля
- `api/services/content_generator.py` - генерация контента
- `api/tasks/analysis_tasks.py` - Celery tasks для анализа

### Приоритет 5: Content Generation

**Эндпоинты для создания:**
- POST /content/generate - генерация поста
- POST /content/variants - несколько вариантов
- POST /content/schedule - планирование публикаций

### Приоритет 6: Telegram Bot Enhancement

Интегрировать новые эндпоинты в Telegram бота:
- Команда для запуска скрапинга
- Уведомления о завершении джобы
- Просмотр статуса в реальном времени

---

## 🐛 Known Issues / Tech Debt

### 1. Error Handling
- Нужно более детальное логирование ошибок в Celery tasks
- Добавить retry механизм для временных ошибок (network issues)

### 2. Performance
- Celery worker сейчас с concurrency=2, можно увеличить
- Добавить кэширование для часто запрашиваемых данных

### 3. Security
- Нужна валидация URLs (защита от SSRF)
- Rate limiting для API эндпоинтов (сейчас только middleware)
- Проверка прав доступа к джобам (user может смотреть только свои)

### 4. Testing
- Добавить unit tests для scrapers
- Integration tests для async tasks
- E2E tests для критичных флоу

---

## 📊 Текущая архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Telegram   │────▶│   FastAPI    │────▶│  PostgreSQL │
│     Bot     │     │      API     │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ├────▶ Redis (Celery broker)
                           │
                           ├────▶ Qdrant (vectors)
                           │
                           ▼
                    ┌──────────────┐
                    │    Celery    │
                    │    Worker    │
                    └──────────────┘
                           │
                           ├────▶ Telegram API (scraping)
                           ├────▶ VK API (scraping)
                           └────▶ Instagram API (scraping)
```

---

## 🔗 Useful Links

- **Swagger UI**: http://localhost:8000/docs
- **Flower UI**: http://localhost:5555
- **Health Check**: http://localhost:8000/health
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## 📝 Quick Commands

```bash
# Start all services
cd infra && docker compose up -d

# Check logs
docker compose logs api -f
docker compose logs celery-worker -f

# Apply migrations
docker compose exec api bash -c "cd /migrations && alembic upgrade head"

# Check database
docker compose exec postgres psql -U aismm -d aismm

# Restart specific service
docker compose restart api
docker compose restart celery-worker

# Rebuild after code changes
docker compose build api celery-worker flower
docker compose up -d
```

---

## 🚀 Ready for Production Checklist

- [ ] Заменить mock scrapers на реальные (Telethon, vk_api, instagrapi)
- [ ] Интегрировать Qdrant для векторного поиска
- [ ] Добавить language detection
- [ ] Реализовать style analysis
- [ ] Создать content generation endpoints
- [ ] Добавить comprehensive error handling
- [ ] Написать unit & integration tests
- [ ] Настроить мониторинг (Prometheus + Grafana)
- [ ] Настроить CI/CD (GitHub Actions)
- [ ] Security audit (OWASP)
- [ ] Load testing (локаст или k6)
- [ ] Documentation (API docs, architecture)

---

## 💡 Ideas for Future

1. **Multi-language support** - генерация контента на разных языках
2. **Content calendar** - планирование публикаций на неделю/месяц
3. **A/B testing** - тестирование разных вариантов постов
4. **Analytics dashboard** - визуализация метрик контента
5. **Team collaboration** - несколько пользователей для одного аккаунта
6. **AI suggestions** - рекомендации по улучшению постов
7. **Hashtag optimization** - подбор оптимальных хэштегов
8. **Competitor analysis** - анализ конкурентов

---

**Текущий статус: T6 Complete ✅ | Прогресс: 60% → 100% (T6 scope)**

**Ветка:** `claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb`

Следующая сессия: Реализация реального скрапинга (T7) или интеграция Qdrant!
