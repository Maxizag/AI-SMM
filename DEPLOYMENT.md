# Инструкции по запуску AI-SMM Agency

## ✅ Проверка конфигурации

Все сервисы настроены и готовы к запуску:

### Сервисы в docker-compose.yml:
1. **postgres** (postgres:16) - База данных
2. **redis** (redis:7) - Кеш и очереди
3. **qdrant** (qdrant/qdrant:latest) - Векторная БД
4. **api** (FastAPI) - REST API сервис
5. **workers** (Celery) - Фоновые задачи
6. **bot** (Telegram Bot) - Бот для пользователей

### Проброшенные порты:
- PostgreSQL: `5432`
- Redis: `6379`
- Qdrant: `6333` (HTTP), `6334` (gRPC)
- API: `8000`

### Зависимости сервисов:
```
api:
  depends_on:
    - postgres (with health check)
    - redis (with health check)
    - qdrant (with health check)

workers:
  depends_on:
    - postgres (with health check)
    - redis (with health check)

bot:
  depends_on:
    - postgres (with health check)
    - api (with health check)
```

## 🚀 Команды для запуска

### На вашей локальной машине выполните:

```bash
# 1. Перейдите в директорию проекта
cd AI-SMM

# 2. Убедитесь, что .env файл настроен
cat .env

# 3. Перейдите в папку infra
cd infra

# 4. Соберите и запустите все сервисы
docker compose up -d --build

# 5. Проверьте статус всех контейнеров
docker compose ps

# 6. Просмотрите логи
docker compose logs -f

# Или логи конкретного сервиса:
docker compose logs -f api
docker compose logs -f postgres
```

## 📊 Ожидаемый вывод `docker compose ps`:

Вы должны увидеть все 6 контейнеров в статусе **Up**:

```
NAME                IMAGE                  STATUS         PORTS
aismm-api           infra-api              Up (healthy)   0.0.0.0:8000->8000/tcp
aismm-bot           infra-bot              Up             -
aismm-postgres      postgres:16            Up (healthy)   0.0.0.0:5432->5432/tcp
aismm-qdrant        qdrant/qdrant:latest   Up (healthy)   0.0.0.0:6333-6334->6333-6334/tcp
aismm-redis         redis:7                Up (healthy)   0.0.0.0:6379->6379/tcp
aismm-workers       infra-workers          Up             -
```

## 🔍 Проверка работоспособности

### 1. Проверьте API health check:
```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:
```json
{
  "status": "ok",
  "service": "api",
  "database": "connected"
}
```

### 2. Откройте Swagger UI:
```bash
# В браузере:
http://localhost:8000/docs
```

### 3. Проверьте базу данных:
```bash
docker exec -it aismm-postgres psql -U aismm -d aismm -c "\dt"
```

Должны увидеть таблицы:
- users
- sources
- style_profiles
- alembic_version

### 4. Проверьте миграции:
```bash
docker exec -it aismm-api bash -c "cd /migrations && alembic current"
```

Должны увидеть: `001 (head)`

## 🧪 Тестирование API

### Создание пользователя:
```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "tg_user_id": 123456789,
    "name": "Test User"
  }'
```

### Получение списка пользователей:
```bash
curl http://localhost:8000/users
```

### Создание источника:
```bash
# Замените USER_ID на UUID из предыдущего запроса
curl -X POST "http://localhost:8000/sources" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "text": "Это тестовый пост для анализа стиля",
    "platform": "telegram"
  }'
```

## 🛠️ Полезные команды

### Просмотр логов:
```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f api
docker compose logs -f postgres
```

### Перезапуск сервиса:
```bash
docker compose restart api
```

### Остановка сервисов:
```bash
docker compose down
```

### Остановка с удалением volumes (очистка данных):
```bash
docker compose down -v
```

### Пересборка конкретного сервиса:
```bash
docker compose up -d --build api
```

### Выполнение команд внутри контейнера:
```bash
# PostgreSQL
docker exec -it aismm-postgres psql -U aismm -d aismm

# API (Python shell)
docker exec -it aismm-api python

# Bash в контейнере API
docker exec -it aismm-api bash
```

## 🐛 Устранение неполадок

### Проблема: Контейнер не запускается
```bash
# Проверьте логи
docker compose logs <service-name>

# Проверьте конфигурацию
docker compose config
```

### Проблема: База данных не подключается
```bash
# Проверьте, что PostgreSQL запущен
docker compose ps postgres

# Проверьте логи PostgreSQL
docker compose logs postgres

# Подключитесь к БД вручную
docker exec -it aismm-postgres psql -U aismm -d aismm
```

### Проблема: Миграции не применились
```bash
# Примените миграции вручную
docker exec -it aismm-api bash -c "cd /migrations && alembic upgrade head"
```

### Проблема: Порт уже занят
```bash
# Проверьте, что порты 5432, 6379, 6333, 8000 свободны
lsof -i :8000
lsof -i :5432

# Или остановите конфликтующие сервисы
```

## 📈 Мониторинг

### Проверка использования ресурсов:
```bash
docker stats
```

### Проверка здоровья контейнеров:
```bash
docker compose ps --format json | jq '.[].Health'
```

## 🎯 Следующие шаги

После успешного запуска всех сервисов:

1. ✅ Протестируйте все API endpoints через Swagger UI
2. ✅ Создайте тестовых пользователей и источники
3. ✅ Проверьте, что данные сохраняются в PostgreSQL
4. ✅ Подготовьтесь к реализации следующих функций
