# ⚙️ Руководство по настройке Celery

## Обзор

Celery настроен для обеспечения устойчивости, масштабируемости и эффективной обработки задач скрапинга. Этот документ описывает все параметры конфигурации и их влияние на работу системы.

---

## Docker Compose конфигурация

### Параметры воркера

```yaml
command: >
  celery -A celery_app worker
  --loglevel=info
  --concurrency=2
  --max-tasks-per-child=100
  --time-limit=600
  --soft-time-limit=540
  --prefetch-multiplier=1
```

### Описание параметров

#### `--concurrency=2`
**Что делает:** Устанавливает количество параллельных worker процессов.

**Почему 2:**
- Баланс между производительностью и потреблением ресурсов
- Достаточно для обработки нескольких источников одновременно
- Не перегружает базу данных и внешние API

**Как изменить:**
```yaml
# Для мощного сервера (8+ CPU cores)
--concurrency=4

# Для слабого сервера или развертывания
--concurrency=1

# Для продакшена с высокой нагрузкой
--concurrency=8
```

**Рекомендация:** `concurrency = CPU_cores - 1` для I/O-bound задач (скрапинг).

---

#### `--max-tasks-per-child=100`
**Что делает:** Каждый worker перезапускается после выполнения 100 задач.

**Почему это важно:**
- Предотвращает утечки памяти
- Очищает незакрытые соединения к БД/API
- Освежает состояние worker'а

**Как это работает:**
1. Worker выполняет 100 задач
2. Worker завершается
3. Celery автоматически запускает новый worker
4. Новый worker получает свежие задачи

**Когда изменить:**
```yaml
# Если задачи очень быстрые (< 1 сек)
--max-tasks-per-child=500

# Если задачи медленные (> 5 мин)
--max-tasks-per-child=50

# Для отладки утечек памяти
--max-tasks-per-child=10
```

---

#### `--time-limit=600`
**Что делает:** Жёсткий лимит времени выполнения задачи (10 минут).

**Что происходит:**
- Если задача выполняется > 10 минут → SIGKILL
- Worker принудительно завершает задачу
- Задача помечается как failed

**Почему 600 секунд:**
- Скрапинг может быть медленным (rate limits, большие каналы)
- 10 минут достаточно для сбора 100 постов
- Защита от зависших задач

**Когда изменить:**
```yaml
# Для быстрых задач
--time-limit=300  # 5 минут

# Для очень больших каналов
--time-limit=1800  # 30 минут

# Для тестирования
--time-limit=60  # 1 минута
```

---

#### `--soft-time-limit=540`
**Что делает:** Мягкий лимит времени (9 минут), отправляет SoftTimeLimitExceeded.

**Почему soft + hard:**
- Soft limit (540s) - задача получает исключение и может gracefully завершиться
- Hard limit (600s) - принудительное завершение через 1 минуту

**Как использовать в коде:**
```python
from celery.exceptions import SoftTimeLimitExceeded

@celery_app.task
def my_task():
    try:
        # Долгая операция
        scrape_large_channel()
    except SoftTimeLimitExceeded:
        # Graceful shutdown
        logger.warning("Task taking too long, saving progress...")
        save_partial_results()
        raise  # Retry later
```

---

#### `--prefetch-multiplier=1`
**Что делает:** Каждый worker забирает только 1 задачу из очереди.

**Почему 1:**
- Задачи скрапинга могут быть длительными (1-10 минут)
- Предотвращает "блокировку" задач в worker'е
- Лучшее распределение нагрузки между worker'ами

**Как это работает:**

**С prefetch=1:**
```
Worker 1: [Task A - 5 min] → берёт Task B после завершения
Worker 2: [Task C - 1 min] → берёт Task D быстро
```

**С prefetch=4 (default):**
```
Worker 1: [Task A, B, C, D] - все в памяти, обрабатывает по очереди
Worker 2: [ждёт] - нет доступных задач
```

**Когда изменить:**
```yaml
# Для быстрых задач (< 10 сек)
--prefetch-multiplier=4

# Для очень длинных задач (> 30 мин)
--prefetch-multiplier=1  # оставить как есть
```

---

#### `C_FORCE_ROOT=true`
**Что делает:** Разрешает запуск Celery от root (в Docker контейнере).

**Почему нужно:**
- Docker контейнеры часто запускаются от root
- Без этого флага Celery откажется запускаться

**Безопасность:**
- В продакшене лучше создать отдельного пользователя
- В dev/staging это безопасно

**Альтернатива (для продакшена):**
```dockerfile
# В Dockerfile
RUN useradd -m celery
USER celery
```

---

### Healthcheck

```yaml
healthcheck:
  test: ["CMD-SHELL", "celery -A celery_app inspect ping -d celery@$$HOSTNAME"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Как работает:**
1. Каждые 30 секунд Docker проверяет здоровье worker'а
2. Отправляет команду `celery inspect ping`
3. Если worker не отвечает 3 раза подряд → контейнер перезапускается

**Преимущества:**
- Автоматическое восстановление после сбоев
- Мониторинг доступности worker'а
- Интеграция с Docker health checks

---

## Retry конфигурация задачи

### Параметры декоратора

```python
@celery_app.task(
    bind=True,
    name='scraping.run_scraping_job',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    default_retry_delay=10
)
def run_scraping_job(self, job_id, user_id, source_ids=None):
    ...
```

### Описание параметров

#### `bind=True`
**Что делает:** Передаёт `self` (task instance) первым аргументом.

**Зачем нужно:**
- Доступ к `self.request.retries` (текущая попытка)
- Доступ к `self.max_retries` (максимум попыток)
- Возможность вызвать `self.retry()` вручную

---

#### `autoretry_for=(Exception,)`
**Что делает:** Автоматически повторяет задачу при любом исключении.

**Как работает:**
1. Задача выбрасывает `Exception`
2. Celery перехватывает исключение
3. Задача автоматически добавляется обратно в очередь с задержкой

**Когда НЕ ретраить:**
```python
from celery.exceptions import Reject

# Не ретраить для бизнес-логики ошибок
if user_not_found:
    raise Reject("User does not exist", requeue=False)
```

**Кастомная логика retry:**
```python
autoretry_for=(ConnectionError, TimeoutError)  # Только сетевые ошибки
```

---

#### `retry_backoff=True`
**Что делает:** Использует экспоненциальный backoff для задержек между попытками.

**Формула:**
```
delay = default_retry_delay * (2 ^ retry_attempt)
```

**Пример (с default_retry_delay=10):**
- Попытка 1 → задержка 10 секунд (10 * 2^0)
- Попытка 2 → задержка 20 секунд (10 * 2^1)
- Попытка 3 → задержка 40 секунд (10 * 2^2)
- Попытка 4 → задержка 60 секунд (ограничено retry_backoff_max)

**Почему экспоненциальный:**
- Даёт системе время восстановиться
- Предотвращает DDoS на внешние API
- Стандартная практика для retry логики

---

#### `retry_backoff_max=60`
**Что делает:** Максимальная задержка между попытками (60 секунд).

**Зачем нужен лимит:**
- Без лимита задержка может вырасти до часов
- 60 секунд - разумный баланс для API rate limits
- Предотвращает слишком долгое ожидание

---

#### `retry_jitter=True`
**Что делает:** Добавляет случайную задержку к backoff.

**Формула:**
```python
delay = backoff_delay + random(0, backoff_delay * 0.1)
```

**Пример:**
- Базовая задержка: 20 секунд
- С jitter: 20-22 секунды (случайно)

**Почему это важно:**
Предотвращает "thundering herd" проблему:
```
Без jitter:
[10:00:00] 100 задач упали
[10:00:20] 100 задач одновременно ретраятся → перегрузка

С jitter:
[10:00:00] 100 задач упали
[10:00:20-22] 100 задач ретраятся постепенно → нормальная нагрузка
```

---

#### `max_retries=3`
**Что делает:** Максимум 3 повторных попытки (всего 4 выполнения).

**Пример lifecycle задачи:**
1. Попытка 1 (исходная) - failed
2. Retry 1 (через 10s) - failed
3. Retry 2 (через 20s) - failed
4. Retry 3 (через 40s) - failed
5. **Task permanently failed**

**Когда изменить:**
```python
# Для критичных задач
max_retries=5

# Для быстрого фейла
max_retries=1

# Бесконечные ретраи (осторожно!)
max_retries=None
```

---

#### `default_retry_delay=10`
**Что делает:** Базовая задержка перед первым retry (10 секунд).

**Взаимодействие с backoff:**
```
Retry 1: 10s
Retry 2: 10 * 2 = 20s
Retry 3: 10 * 4 = 40s
```

---

## Логирование и мониторинг

### Логирование retry попыток

Код автоматически логирует информацию о retry:

```python
if self.request.retries > 0:
    logger.info(
        f"Retrying scraping job {job_id} - attempt {self.request.retries + 1}/{self.max_retries + 1}"
    )
```

**Пример лога:**
```
INFO: Retrying scraping job 550e8400-... - attempt 2/4
INFO: Scraping source abc123... (retry after connection timeout)
```

### Мониторинг через Flower

Flower UI доступен на `http://localhost:5555`:

**Основные метрики:**
- Active tasks - текущие выполняющиеся задачи
- Failed tasks - проваленные задачи
- Retried tasks - задачи с retry
- Worker status - состояние воркеров

**Полезные страницы:**
- `/tasks` - все задачи
- `/workers` - статус воркеров
- `/monitor` - реалтайм мониторинг

---

## Рекомендации по масштабированию

### Низкая нагрузка (< 10 пользователей)
```yaml
--concurrency=1
--max-tasks-per-child=100
```

### Средняя нагрузка (10-100 пользователей)
```yaml
--concurrency=2
--max-tasks-per-child=100
```

### Высокая нагрузка (100-1000 пользователей)
```yaml
--concurrency=4
--max-tasks-per-child=200

# + добавить второй worker контейнер в docker-compose
```

### Очень высокая нагрузка (1000+ пользователей)
```yaml
# Используйте Kubernetes или Docker Swarm
# Запустите 3-5 worker контейнеров
# Каждый с --concurrency=4

# + добавьте приоритетные очереди:
celery -A celery_app worker -Q high_priority,default
```

---

## Продвинутые настройки

### Приоритетные очереди

```python
# В celery_app.py
app.conf.task_routes = {
    'scraping.run_scraping_job': {'queue': 'scraping'},
    'other.important_task': {'queue': 'high_priority'},
}

# В docker-compose.yml
command: celery -A celery_app worker -Q high_priority,scraping,default
```

### Rate limiting

```python
@celery_app.task(rate_limit='10/m')  # 10 задач в минуту
def rate_limited_task():
    pass
```

### Task routing по типу

```python
app.conf.task_routes = {
    'scraping.*': {'queue': 'scraping'},
    'generation.*': {'queue': 'generation'},
    '*': {'queue': 'default'}
}
```

---

## Отладка проблем

### Worker не запускается

**Проверьте:**
```bash
docker-compose logs celery-worker
```

**Частые причины:**
- Redis недоступен
- Неправильный REDIS_URL
- Синтаксическая ошибка в celery_app.py

---

### Задачи зависают

**Проверьте:**
1. Логи worker'а: `docker-compose logs -f celery-worker`
2. Flower UI: http://localhost:5555/tasks
3. Healthcheck статус: `docker inspect aismm-celery-worker`

**Решение:**
- Уменьшите `--time-limit`
- Добавьте logging в задачу
- Проверьте блокирующие операции (sync code в async)

---

### Утечки памяти

**Симптомы:**
- Worker использует всё больше RAM
- OOMKiller убивает контейнер

**Решение:**
1. Уменьшите `--max-tasks-per-child` до 50
2. Добавьте мониторинг памяти
3. Проверьте незакрытые соединения к БД

```python
# Плохо
db_session = get_session()  # Не закрыт!

# Хорошо
async with AsyncSessionLocal() as session:
    # Автоматически закроется
```

---

### Redis переполнен задачами

**Проверьте размер очереди:**
```bash
docker-compose exec redis redis-cli
> LLEN celery
```

**Решение:**
```bash
# Очистить очередь (ОСТОРОЖНО!)
celery -A celery_app purge

# Или через redis
redis-cli FLUSHDB
```

---

## Чеклист для продакшена

- [ ] Настроены ограничения памяти в docker-compose
- [ ] Healthcheck'и работают
- [ ] Логи пишутся в файлы/ELK
- [ ] Flower защищён паролем
- [ ] Rate limits настроены для внешних API
- [ ] Мониторинг настроен (Prometheus/Grafana)
- [ ] Alerting для Failed tasks
- [ ] Backup очередей Redis
- [ ] Graceful shutdown настроен

---

## Полезные команды

```bash
# Проверить статус воркеров
celery -A celery_app inspect active

# Статистика
celery -A celery_app inspect stats

# Отменить все задачи
celery -A celery_app purge

# Отменить конкретную задачу
celery -A celery_app control revoke <task_id>

# Посмотреть зарегистрированные задачи
celery -A celery_app inspect registered

# Ping всех воркеров
celery -A celery_app inspect ping
```
