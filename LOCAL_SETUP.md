# 🏠 Настройка для локальной разработки

## Шаг 1: Получите последние изменения

```bash
cd /Users/capybara/Projects/AI-SMM/AI-SMM
git fetch origin claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb
git pull origin claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb
```

## Шаг 2: Проверьте ваш .env файл

```bash
cat .env
```

Убедитесь, что там есть:
```
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aismm
POSTGRES_USER=aismm
POSTGRES_PASSWORD=devpass
```

Если .env файла нет, создайте его:
```bash
cp .env.example .env
# Отредактируйте .env и добавьте ваши ключи API
```

## Шаг 3: Запустите сервисы

```bash
docker-compose up -d
```

Проверьте статус:
```bash
docker-compose ps
```

Должны работать:
- ✓ postgres
- ✓ redis
- ✓ api
- ✓ celery_worker

## Шаг 4: Проверьте подключение к базе данных

```bash
# Используйте креденшалы из вашего .env
docker-compose exec postgres psql -U aismm -d aismm
```

В psql выполните:
```sql
-- Посмотреть все таблицы
\dt

-- Посмотреть статистику
SELECT 'users' as table, COUNT(*) FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts;

-- Выйти
\q
```

## Шаг 5: Очистка базы данных

### Самый простой способ (автоматический)

```bash
./clear_db_auto.sh
```

Этот скрипт:
- ✅ Автоматически определяет креденшалы из .env
- ✅ Показывает статистику до и после
- ✅ Просит подтверждение
- ✅ Удаляет все данные кроме пользователей

### Ручная очистка через SQL

```bash
docker-compose exec postgres psql -U aismm -d aismm
```

Затем:
```sql
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
-- DELETE FROM users;  -- раскомментировать для удаления пользователей

-- Проверить результат
SELECT 'users' as table, COUNT(*) FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts;

\q
```

### Через прямой SQL-скрипт

```bash
docker-compose exec -T postgres psql -U aismm -d aismm << 'EOF'
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
SELECT 'users' as table, COUNT(*) FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts;
EOF
```

## Шаг 6: Тестирование

### Получить токен
```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tg_user_id": 123456789, "tg_username": "testuser"}'
```

Сохраните `access_token` из ответа.

### Добавить источник
```bash
export TOKEN="ваш_access_token_здесь"

curl -X POST http://localhost:8000/api/v1/onboarding/sources/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://t.me/durov"]}'
```

### Проверить источники
```bash
curl -X GET http://localhost:8000/api/v1/onboarding/sources \
  -H "Authorization: Bearer $TOKEN"
```

### Запустить скрапинг
```bash
curl -X POST http://localhost:8000/api/v1/onboarding/start-scraping \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_posts": 50, "min_posts": 25}'
```

Сохраните `job_id` из ответа.

### Проверить статус скрапинга
```bash
export JOB_ID="ваш_job_id_здесь"

curl -X GET "http://localhost:8000/api/v1/onboarding/scraping-status/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN"
```

## Проверка логов

```bash
# Логи API
docker-compose logs -f api

# Логи Celery
docker-compose logs -f celery_worker

# Логи PostgreSQL
docker-compose logs -f postgres

# Все логи сразу
docker-compose logs -f
```

## Частые проблемы

### ❌ role "ai_smm_user" does not exist

**Причина:** Вы используете неправильные креденшалы.

**Решение:** Проверьте ваш .env файл и используйте правильные значения:
```bash
cat .env | grep POSTGRES
```

Затем используйте эти значения для подключения:
```bash
docker-compose exec postgres psql -U [POSTGRES_USER] -d [POSTGRES_DB]
```

### ❌ ./clear_db_auto.sh: No such file or directory

**Причина:** Вы не сделали git pull с последними изменениями.

**Решение:**
```bash
git pull origin claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb
```

### ❌ Контейнеры не запущены

**Решение:**
```bash
docker-compose up -d
docker-compose ps
```

### ❌ Connection refused при обращении к API

**Причина:** API контейнер не запущен или не готов.

**Решение:**
```bash
# Проверить статус
docker-compose ps api

# Посмотреть логи
docker-compose logs api

# Перезапустить
docker-compose restart api
```

## Полезные команды

```bash
# Пересобрать контейнеры
docker-compose build

# Перезапустить все сервисы
docker-compose restart

# Остановить все
docker-compose down

# Остановить и удалить volumes (ОСТОРОЖНО! Удалит все данные БД)
docker-compose down -v

# Посмотреть использование ресурсов
docker stats
```
