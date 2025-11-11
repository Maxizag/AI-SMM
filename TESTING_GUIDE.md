# 🧪 Руководство по очистке данных и тестированию

## 📋 Содержание
1. [Очистка базы данных](#очистка-базы-данных)
2. [Тестирование системы](#тестирование-системы)
3. [Проверка результатов](#проверка-результатов)

---

## 🗑️ Очистка базы данных

### Вариант 1: Очистка через скрипт (Рекомендуется)

#### Показать текущую статистику БД
```bash
cd /home/user/AI-SMM
python -m api.utils.clear_database --stats
```

#### Очистить только контент (оставить пользователей)
```bash
python -m api.utils.clear_database --keep-users
```
Это удалит:
- ✓ Все посты
- ✓ Все источники
- ✓ Все задания скрапинга
- ✓ Все брифы и стилевые профили
- ✗ Пользователи ОСТАНУТСЯ

#### Полная очистка (включая пользователей)
```bash
python -m api.utils.clear_database --all
```

#### Очистка данных конкретного пользователя
```bash
python -m api.utils.clear_database --user-id "UUID_ПОЛЬЗОВАТЕЛЯ"
```

### Вариант 2: Прямая очистка через psql

```bash
# Подключиться к базе
docker-compose exec postgres psql -U ai_smm_user -d ai_smm_db

# Выполнить очистку
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
-- Если нужно удалить и пользователей:
-- DELETE FROM users;

# Проверить результат
SELECT
    'users' as table, COUNT(*) FROM users
UNION ALL
SELECT 'sources', COUNT(*) FROM sources
UNION ALL
SELECT 'posts', COUNT(*) FROM posts
UNION ALL
SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs;

\q
```

---

## 🧪 Тестирование системы

### Шаг 1: Убедитесь, что все сервисы запущены

```bash
cd /home/user/AI-SMM
docker-compose ps
```

Должны работать:
- ✓ api (FastAPI)
- ✓ postgres
- ✓ redis
- ✓ celery_worker

Если что-то не запущено:
```bash
docker-compose up -d
```

### Шаг 2: Проверьте логи сервисов

```bash
# API логи
docker-compose logs -f api

# Celery логи
docker-compose logs -f celery_worker

# Все логи
docker-compose logs -f
```

### Шаг 3: Тестирование через Telegram бота

#### 3.1 Создание тестового пользователя

Запустите бота и отправьте команду:
```
/start
```

#### 3.2 Добавление источников

Отправьте URL источников для тестирования:

**Telegram канал:**
```
https://t.me/durov
```

**VK группа:**
```
https://vk.com/apiclub
```

**Instagram:**
```
https://www.instagram.com/instagram/
```

#### 3.3 Проверка статуса источников

Бот должен показать статусы:
- `new` → `verified` → `scraping` → `done`

### Шаг 4: Тестирование через API напрямую

#### 4.1 Получить токен авторизации

```bash
# Замените TG_USER_ID на ваш Telegram ID
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tg_user_id": 123456789, "tg_username": "testuser"}'
```

Сохраните полученный `access_token`.

#### 4.2 Добавить источник

```bash
export TOKEN="ваш_access_token"

curl -X POST http://localhost:8000/api/v1/onboarding/sources/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://t.me/durov"]
  }'
```

#### 4.3 Проверить список источников

```bash
curl -X GET http://localhost:8000/api/v1/onboarding/sources \
  -H "Authorization: Bearer $TOKEN"
```

#### 4.4 Запустить скрапинг

```bash
curl -X POST http://localhost:8000/api/v1/onboarding/start-scraping \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_posts": 50,
    "min_posts": 25
  }'
```

Ответ будет содержать `job_id`. Сохраните его.

#### 4.5 Проверить статус задания

```bash
export JOB_ID="полученный_job_id"

curl -X GET "http://localhost:8000/api/v1/onboarding/scraping-status/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN"
```

---

## ✅ Проверка результатов

### 1. Проверка через базу данных

```bash
docker-compose exec postgres psql -U ai_smm_user -d ai_smm_db
```

```sql
-- Статистика по источникам
SELECT
    platform,
    status,
    COUNT(*) as count
FROM sources
GROUP BY platform, status
ORDER BY platform, status;

-- Статистика по постам
SELECT
    p.platform,
    COUNT(*) as posts_count,
    s.url as source_url
FROM posts p
JOIN sources s ON p.source_id = s.id
GROUP BY p.platform, s.url
ORDER BY posts_count DESC;

-- Статус заданий скрапинга
SELECT
    id,
    status,
    target_posts,
    total_collected,
    created_at,
    completed_at
FROM scraping_jobs
ORDER BY created_at DESC;

-- Последние добавленные посты
SELECT
    platform,
    author_handle,
    LEFT(text, 50) as preview,
    posted_at,
    created_at
FROM posts
ORDER BY created_at DESC
LIMIT 10;
```

### 2. Проверка дедупликации источников

```sql
-- Проверить, что нет дублей по URL
SELECT
    user_id,
    url,
    COUNT(*) as count
FROM sources
GROUP BY user_id, url
HAVING COUNT(*) > 1;

-- Должен вернуть 0 строк - дублей быть не должно!
```

### 3. Проверка форматов данных

```sql
-- Проверить формат постов Telegram
SELECT
    platform,
    platform_post_id,
    author_handle,
    text,
    media,
    reactions
FROM posts
WHERE platform = 'telegram'
LIMIT 3;

-- Проверить, что все обязательные поля заполнены
SELECT
    COUNT(*) as total,
    COUNT(platform_post_id) as with_post_id,
    COUNT(text) as with_text,
    COUNT(posted_at) as with_date
FROM posts;
```

### 4. Мониторинг производительности

```bash
# Следить за логами в реальном времени
docker-compose logs -f celery_worker | grep -i "scraped\|error\|completed"

# Проверить использование ресурсов
docker stats
```

---

## 🐛 Решение проблем

### Проблема: Источники не добавляются

**Проверьте:**
1. API работает: `curl http://localhost:8000/health`
2. Redis работает: `docker-compose ps redis`
3. Логи API: `docker-compose logs api`

### Проблема: Скрапинг не запускается

**Проверьте:**
1. Celery работает: `docker-compose ps celery_worker`
2. Redis доступен: `docker-compose exec redis redis-cli ping`
3. Логи Celery: `docker-compose logs celery_worker`

### Проблема: Дублирующиеся источники

**Решение:**
1. Очистите дубли через скрипт:
```bash
python -m api.utils.clear_database --keep-users
```
2. Добавьте источники заново

### Проблема: Посты не сохраняются

**Проверьте:**
1. Права доступа к источнику (приватный канал?)
2. Правильность URL
3. Логи скрапера:
```bash
docker-compose logs celery_worker | grep -A 10 "scraping"
```

---

## 📊 Ожидаемые результаты тестирования

После успешного тестирования вы должны увидеть:

✅ **База данных:**
- Пользователь создан
- Источники со статусом `done`
- Посты собраны (минимум `min_posts`)
- Задание скрапинга со статусом `done` или `partial`

✅ **API:**
- Все эндпоинты отвечают без ошибок 500
- Дедупликация работает (нет дублей источников)
- Корректные форматы ответов

✅ **Скрапинг:**
- Celery задачи выполняются
- Данные сохраняются в базу
- Нет критических ошибок в логах

---

## 📝 Чеклист перед продакшеном

- [ ] Все тесты пройдены
- [ ] Дедупликация источников работает
- [ ] Нет дублей в базе данных
- [ ] Celery задачи выполняются стабильно
- [ ] API возвращает корректные ошибки
- [ ] Логирование настроено
- [ ] Переменные окружения проверены
- [ ] Миграции применены
- [ ] Бэкап базы данных настроен

---

## 🔄 Автоматический тест-скрипт

Создайте файл `test_flow.sh`:

```bash
#!/bin/bash

echo "=== Начало тестирования ==="

# 1. Очистка базы
echo "Очистка базы данных..."
python -m api.utils.clear_database --keep-users

# 2. Проверка сервисов
echo "Проверка сервисов..."
docker-compose ps

# 3. Получение токена
echo "Получение токена..."
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tg_user_id": 123456789, "tg_username": "testuser"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"

# 4. Добавление источника
echo "Добавление источника..."
curl -X POST http://localhost:8000/api/v1/onboarding/sources/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://t.me/durov"]}'

# 5. Запуск скрапинга
echo "Запуск скрапинга..."
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/onboarding/start-scraping \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_posts": 10, "min_posts": 5}' \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 6. Ожидание и проверка статуса
echo "Ожидание завершения (30 сек)..."
sleep 30

curl -X GET "http://localhost:8000/api/v1/onboarding/scraping-status/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo "=== Тестирование завершено ==="
```

Запуск:
```bash
chmod +x test_flow.sh
./test_flow.sh
```
