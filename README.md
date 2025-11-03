# AI-SMM Agency

Система для генерации SMM-контента в стиле конкретного автора с использованием AI.

## Архитектура

Проект состоит из следующих компонентов:

- **API** (FastAPI) - REST API для работы с данными
- **Workers** (Celery) - Фоновые задачи для обработки контента
- **Bot** (Telegram Bot) - Интерфейс для взаимодействия с пользователями
- **PostgreSQL** - Основная база данных
- **Redis** - Кеширование и очереди задач
- **Qdrant** - Векторная база данных для поиска похожих постов

## Структура проекта

```
AI-SMM/
├── api/              # FastAPI приложение
│   ├── main.py       # Основное приложение
│   ├── models.py     # SQLAlchemy модели
│   ├── schemas.py    # Pydantic схемы
│   ├── database.py   # Настройка подключения к БД
│   ├── config.py     # Конфигурация
│   └── Dockerfile
├── workers/          # Celery workers
│   └── Dockerfile
├── bot/              # Telegram bot
│   └── Dockerfile
├── migrations/       # Alembic миграции
│   ├── versions/
│   └── env.py
├── infra/            # Docker Compose конфигурация
│   └── docker-compose.yml
└── .env.example      # Пример переменных окружения
```

## База данных

### Таблицы:

**users**
- `id` (UUID, PK)
- `tg_user_id` (BIGINT, UNIQUE)
- `name` (VARCHAR)
- `created_at` (TIMESTAMP)

**sources**
- `id` (UUID, PK)
- `user_id` (UUID, FK -> users.id)
- `text` (TEXT)
- `platform` (VARCHAR)
- `created_at` (TIMESTAMP)

**style_profiles**
- `id` (UUID, PK)
- `user_id` (UUID, FK -> users.id)
- `json` (JSONB)
- `created_at` (TIMESTAMP)

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repository-url>
cd AI-SMM
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактируйте .env файл, добавив необходимые API ключи
```

### 3. Запустить сервисы

```bash
cd infra
docker compose up -d
```

Это запустит все сервисы:
- PostgreSQL на порту 5432
- Redis на порту 6379
- Qdrant на портах 6333 (HTTP) и 6334 (gRPC)
- API на порту 8000
- Workers и Bot в фоновом режиме

### 4. Применить миграции

Миграции применяются автоматически при запуске API сервиса.

Для ручного применения:

```bash
docker exec -it aismm-api bash
cd /migrations
alembic upgrade head
```

### 5. Проверить работу API

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Документация API
open http://localhost:8000/docs
```

## API Endpoints

### Health Check
- `GET /health` - Проверка состояния сервиса

### Users
- `POST /users` - Создать пользователя
- `GET /users/{user_id}` - Получить пользователя
- `GET /users` - Список пользователей

### Sources
- `POST /sources` - Создать источник
- `GET /sources/{source_id}` - Получить источник
- `GET /users/{user_id}/sources` - Список источников пользователя

### Style Profiles
- `POST /style-profiles` - Создать профиль стиля
- `GET /style-profiles/{profile_id}` - Получить профиль
- `GET /users/{user_id}/style-profiles` - Список профилей пользователя

## Разработка

### Создание новой миграции

```bash
cd migrations
alembic revision --autogenerate -m "Description"
```

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f api
```

### Остановка сервисов

```bash
docker compose down          # Остановить сервисы
docker compose down -v       # Остановить и удалить volumes
```

## Технологии

- **Python 3.11**
- **FastAPI** - Современный web-фреймворк
- **SQLAlchemy 2.0** - ORM с async поддержкой
- **Alembic** - Миграции БД
- **PostgreSQL 16** - Основная БД
- **Redis 7** - Кеш и очереди
- **Qdrant** - Векторная БД
- **Docker & Docker Compose** - Контейнеризация

## Лицензия

MIT
