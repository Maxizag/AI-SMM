# 🚨 Руководство по обработке ошибок скрапинга

## Обзор

Система скрапинга теперь предоставляет структурированные коды ошибок с actionable сообщениями для пользователей. Это позволяет фронтенду/боту показывать понятные инструкции, как решить проблему.

## Коды ошибок

### Ошибки на уровне источника (Source-level)

#### `PLATFORM_PRIVATE`
**Когда возникает:** Аккаунт закрыт или приватный, доступ к постам ограничен.

**Сообщение:**
```
Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами
(минимум 50 постов). Используйте /ingest/manual_posts для загрузки.
```

**Что делать:**
1. Открыть профиль на платформе на время скрапинга
2. Загрузить посты вручную через `POST /ingest/manual_posts`
3. Добавить другой публичный источник

**Пример ответа:**
```json
{
  "code": "PLATFORM_PRIVATE",
  "message": "Аккаунт закрыт. Откройте профиль на время...",
  "source_id": "uuid-source-id",
  "platform": "instagram"
}
```

---

#### `PLATFORM_INVALID_URL`
**Когда возникает:** URL имеет неправильный формат или не поддерживается.

**Сообщение:**
```
Неверный формат ссылки. Проверьте URL и попробуйте снова.
```

**Что делать:**
1. Проверить формат URL (например, `https://t.me/channel`, `https://vk.com/club123`)
2. Убедиться, что платформа поддерживается (telegram, vk, instagram)

---

#### `PLATFORM_NOT_FOUND`
**Когда возникает:** Аккаунт/канал не существует или был удалён.

**Сообщение:**
```
Аккаунт не найден. Убедитесь, что ссылка правильная и аккаунт существует.
```

---

#### `PLATFORM_INSUFFICIENT_CONTENT`
**Когда возникает:** В источнике меньше 50 постов.

**Сообщение:**
```
В источнике недостаточно постов (меньше 50). Добавьте ещё ссылку или
загрузите архив постов через /ingest/manual_posts.
```

**Что делать:**
1. Добавить дополнительный источник
2. Загрузить посты вручную
3. Использовать референсы через `/ingest/hints`

---

#### `PLATFORM_ACCESS_DENIED`
**Когда возникает:** Доступ к источнику ограничен (например, нужна подписка).

**Сообщение:**
```
Доступ к источнику ограничен. Проверьте, что аккаунт публичный или
предоставьте доступ для скрапинга.
```

---

#### `PLATFORM_RATE_LIMIT`
**Когда возникает:** Превышен лимит запросов к API платформы.

**Сообщение:**
```
Превышен лимит запросов к платформе. Попробуйте через 15-30 минут.
```

---

#### `PLATFORM_UNAVAILABLE`
**Когда возникает:** Платформа временно недоступна.

**Сообщение:**
```
Платформа временно недоступна. Попробуйте позже.
```

---

### Ошибки на уровне задания (Job-level)

#### `JOB_INSUFFICIENT_POSTS`
**Когда возникает:** Суммарно собрано меньше 50 постов (рекомендуемый минимум для качественного анализа).

**Сообщение:**
```
Собрано недостаточно постов для качественного анализа стиля.
Рекомендации:
• Добавьте ещё 1-2 источника
• Загрузите архив постов через /ingest/manual_posts
• Укажите референсы для вдохновения через /ingest/hints

Минимум 50 постов требуется для хорошего качества стиля.
```

**Статусы джобы:**
- `partial` - если собрано >= min_posts, но < 50
- `error` - если собрано < min_posts

**Что делать:**
1. Добавить больше источников через `POST /sources/v2`
2. Загрузить посты вручную через `POST /ingest/manual_posts`
3. Добавить референсы через `POST /ingest/hints`

---

#### `JOB_NO_SOURCES`
**Когда возникает:** Нет доступных источников для скрапинга.

**Сообщение:**
```
Нет источников для скрапинга. Добавьте хотя бы один источник через /sources/v2.
```

---

#### `JOB_ALL_SOURCES_FAILED`
**Когда возникает:** Все источники вернули ошибку, ни один пост не собран.

**Сообщение:**
```
Не удалось собрать посты ни из одного источника. Проверьте доступность
источников и попробуйте снова.
```

---

### Системные ошибки

#### `INTERNAL_ERROR`
**Когда возникает:** Внутренняя ошибка системы.

**Сообщение:**
```
Внутренняя ошибка системы. Попробуйте позже или обратитесь в поддержку.
```

---

## Структура ответа API

### GET /ingest/status?job_id={uuid}

**Успешный ответ (done):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "progress": {
    "total_collected": 120,
    "by_source": [
      {
        "source_id": "uuid1",
        "platform": "telegram",
        "collected": 80,
        "status": "done"
      },
      {
        "source_id": "uuid2",
        "platform": "vk",
        "collected": 40,
        "status": "done"
      }
    ],
    "summary": {
      "total_sources": 2,
      "private_sources": 0,
      "failed_sources": 0,
      "successful_sources": 2,
      "total_collected": 120,
      "quality_sufficient": true
    }
  },
  "errors": []
}
```

**Частичный успех (partial) с предупреждением:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "partial",
  "progress": {
    "total_collected": 35,
    "by_source": [
      {
        "source_id": "uuid1",
        "platform": "telegram",
        "collected": 35,
        "status": "done"
      }
    ],
    "summary": {
      "total_sources": 1,
      "private_sources": 0,
      "failed_sources": 0,
      "successful_sources": 1,
      "total_collected": 35,
      "quality_sufficient": false
    }
  },
  "errors": [
    {
      "code": "JOB_INSUFFICIENT_POSTS",
      "message": "Собрано недостаточно постов для качественного анализа стиля. Рекомендации:\n• Добавьте ещё 1-2 источника\n• Загрузите архив постов через /ingest/manual_posts\n• Укажите референсы для вдохновения через /ingest/hints\n\nМинимум 50 постов требуется для хорошего качества стиля.",
      "context": {
        "total_collected": 35,
        "min_required": 50
      }
    }
  ]
}
```

**Ошибка с приватным источником:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "progress": {
    "total_collected": 0,
    "by_source": [
      {
        "source_id": "uuid1",
        "platform": "instagram",
        "collected": 0,
        "status": "error",
        "error_code": "PLATFORM_PRIVATE"
      }
    ],
    "summary": {
      "total_sources": 1,
      "private_sources": 1,
      "failed_sources": 0,
      "successful_sources": 0,
      "total_collected": 0,
      "quality_sufficient": false
    }
  },
  "errors": [
    {
      "code": "PLATFORM_PRIVATE",
      "message": "Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами (минимум 50 постов). Используйте /ingest/manual_posts для загрузки.",
      "source_id": "uuid1",
      "platform": "instagram"
    },
    {
      "code": "JOB_ALL_SOURCES_FAILED",
      "message": "Не удалось собрать посты ни из одного источника. Проверьте доступность источников и попробуйте снова."
    }
  ]
}
```

---

## Примеры использования

### 1. Обработка в боте

```python
import httpx

async def check_scraping_status(job_id: str):
    response = await httpx.get(
        f"http://api:8000/api/v1/ingest/status?job_id={job_id}"
    )
    data = response.json()

    status = data["status"]
    errors = data["errors"]
    summary = data["progress"].get("summary", {})

    if status == "done":
        if summary.get("quality_sufficient"):
            return "✅ Скрапинг завершён! Собрано достаточно постов для анализа."
        else:
            # Есть предупреждение о недостаточном количестве
            return format_warnings(errors)

    elif status == "partial":
        return format_partial_result(data)

    elif status == "error":
        return format_errors(errors)

    else:  # queued, running
        return f"⏳ Скрапинг в процессе... Собрано {summary.get('total_collected', 0)} постов"


def format_errors(errors):
    """Форматирует ошибки для отображения пользователю"""
    messages = []

    for error in errors:
        code = error.get("code")
        message = error.get("message")

        if code == "PLATFORM_PRIVATE":
            messages.append(f"🔒 {message}")
        elif code == "JOB_INSUFFICIENT_POSTS":
            messages.append(f"⚠️ {message}")
        else:
            messages.append(f"❌ {message}")

    return "\n\n".join(messages)
```

### 2. Обработка на фронтенде (React/TypeScript)

```typescript
interface ScrapingError {
  code: string;
  message: string;
  source_id?: string;
  platform?: string;
  context?: Record<string, any>;
}

interface JobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'partial' | 'error';
  progress: {
    total_collected: number;
    by_source: Array<any>;
    summary?: {
      quality_sufficient: boolean;
      private_sources: number;
      failed_sources: number;
    };
  };
  errors: ScrapingError[];
}

function renderScrapingErrors(status: JobStatus) {
  const { errors, progress } = status;

  return (
    <div>
      {errors.map((error, idx) => {
        switch (error.code) {
          case 'PLATFORM_PRIVATE':
            return (
              <Alert key={idx} severity="error" icon={<LockIcon />}>
                <AlertTitle>Закрытый профиль</AlertTitle>
                {error.message}
                <Box mt={2}>
                  <Button onClick={() => uploadManualPosts()}>
                    Загрузить посты вручную
                  </Button>
                </Box>
              </Alert>
            );

          case 'JOB_INSUFFICIENT_POSTS':
            return (
              <Alert key={idx} severity="warning" icon={<WarningIcon />}>
                <AlertTitle>Недостаточно постов</AlertTitle>
                {error.message}
                <Box mt={2}>
                  <Button onClick={() => addMoreSources()}>
                    Добавить источник
                  </Button>
                  <Button onClick={() => uploadManualPosts()}>
                    Загрузить посты
                  </Button>
                </Box>
              </Alert>
            );

          default:
            return (
              <Alert key={idx} severity="error">
                {error.message}
              </Alert>
            );
        }
      })}
    </div>
  );
}
```

---

## Тестирование

### Ручное тестирование через API

```bash
# 1. Создать тестового пользователя
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"tg_user_id": 123, "tg_username": "testuser"}'

export TOKEN="полученный_токен"

# 2. Добавить приватный источник (симулируем)
# (В реальности нужно мокировать scraper.verify() для возврата is_private=True)

# 3. Запустить скрапинг
curl -X POST http://localhost:8000/api/v1/ingest/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "uuid-пользователя",
    "source_ids": [],
    "target_posts": 100,
    "min_posts": 50
  }'

export JOB_ID="полученный_job_id"

# 4. Проверить статус
curl http://localhost:8000/api/v1/ingest/status?job_id=$JOB_ID
```

---

## Миграция со старой версии

Если у вас есть код, который ожидает `errors: list[str]`, он продолжит работать благодаря обратной совместимости:

```python
# Старый код (работает)
for error in job.errors:
    print(error)  # Может быть строка или dict

# Новый код (рекомендуется)
for error in job.errors:
    if isinstance(error, dict):
        print(f"[{error['code']}] {error['message']}")
    else:
        print(error)
```

---

## Дальнейшие улучшения

1. **Retry механизм** для `PLATFORM_RATE_LIMIT`
2. **Webhook уведомления** при завершении джобы
3. **Автоматическая загрузка из архива** для Telegram
4. **Интеграция с платными API** для приватных Instagram/VK
5. **ML-предсказание качества** на основе количества постов
