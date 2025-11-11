# Спецификация API статусов для бота

## Эндпоинт: GET /ingest/status?job_id={uuid}

### Текущая структура ответа

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": {
    "total_collected": 45,
    "by_source": [
      {
        "source_id": "uuid-1",
        "platform": "telegram",
        "collected": 30,
        "status": "done",
        "error_code": null
      },
      {
        "source_id": "uuid-2",
        "platform": "instagram",
        "collected": 0,
        "status": "error",
        "error_code": "PLATFORM_PRIVATE"
      },
      {
        "source_id": "uuid-3",
        "platform": "vk",
        "collected": 15,
        "status": "running",
        "error_code": null
      }
    ],
    "summary": {
      "total_sources": 3,
      "private_sources": 1,
      "failed_sources": 0,
      "successful_sources": 1,
      "total_collected": 45,
      "quality_sufficient": false
    }
  },
  "errors": [
    {
      "code": "PLATFORM_PRIVATE",
      "message": "Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами (минимум 50 постов). Используйте /ingest/manual_posts для загрузки.",
      "source_id": "uuid-2",
      "platform": "instagram"
    }
  ]
}
```

## Чего не хватает для UX бота

### Проблема
Бот должен показывать сообщение об ошибке для каждого источника в `by_source[]`, но сейчас:
- В `by_source[].error_code` есть только код (например, "PLATFORM_PRIVATE")
- Само сообщение нужно искать в общем массиве `errors[]` по `source_id`

Это создает неудобство для бота:
```python
# Сейчас бот должен делать так:
for source in progress['by_source']:
    if source['status'] == 'error':
        error_code = source.get('error_code')
        # Поиск сообщения в общем массиве
        error_message = None
        for error in errors:
            if error.get('source_id') == source['source_id']:
                error_message = error['message']
                break
        # Показать пользователю
```

### Предлагаемое решение

Добавить `error_message` прямо в `by_source[]`:

```json
{
  "by_source": [
    {
      "source_id": "uuid-2",
      "platform": "instagram",
      "collected": 0,
      "status": "error",
      "error_code": "PLATFORM_PRIVATE",
      "error_message": "Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами (минимум 50 постов). Используйте /ingest/manual_posts для загрузки."
    }
  ]
}
```

Тогда бот может просто:
```python
for source in progress['by_source']:
    if source['status'] == 'error':
        show_error(source['error_message'])
```

## UX-сценарии для бота

### 1. Статус: queued
```
Текст: "⏳ Задание поставлено в очередь..."
Кнопки: [Отменить]
```

### 2. Статус: running
```
Текст: "🔄 Собираем посты... (45/100)"

По источникам:
✅ Telegram @channel - 30 постов
🔄 VK club123 - 15 постов
❌ Instagram user - закрыт

Кнопки: [Обновить статус]
```

### 3. Статус: done (quality_sufficient=true)
```
Текст: "✅ Готово! Собрано 120 постов"
Кнопки: [Перейти к следующему шагу]
```

### 4. Статус: done (quality_sufficient=false)
```
Текст: "⚠️ Собрано только 35 постов (рекомендуется минимум 50)"

Рекомендации:
• Добавьте ещё 1-2 источника
• Загрузите архив постов
• Укажите референсы для вдохновения

Кнопки: [Добавить источник] [Загрузить посты] [Продолжить всё равно]
```

### 5. Статус: partial
```
Текст: "⚠️ Часть источников недоступна"

Собрано 35 постов из 3 источников:
✅ Telegram @channel - 35 постов
❌ Instagram user - закрыт

Рекомендации:
• Откройте Instagram профиль временно
• Или загрузите файл с постами

Кнопки: [Добавить источник] [Загрузить посты] [Продолжить]
```

### 6. Статус: error
```
Текст: "❌ Не удалось собрать посты"

Instagram @user:
🔒 Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами.

VK club123:
❌ Неверный формат ссылки. Проверьте URL и попробуйте снова.

Кнопки: [Изменить источники] [Загрузить посты вручную]
```

## Требования к полям

### Обязательные поля

#### progress.total_collected
- Тип: `int`
- Всегда присутствует
- Используется для показа прогресса

#### progress.by_source[]
Массив объектов с полями:
- `source_id`: UUID (string)
- `platform`: telegram|vk|instagram|manual
- `collected`: int
- `status`: queued|running|done|error
- `error_code`: string | null (опционально)
- `error_message`: string | null (**НУЖНО ДОБАВИТЬ**)

#### progress.summary
- `total_sources`: int
- `private_sources`: int
- `failed_sources`: int
- `successful_sources`: int
- `total_collected`: int
- `quality_sufficient`: bool

#### status
Возможные значения:
- `queued` - в очереди
- `running` - выполняется
- `done` - успешно завершено
- `partial` - частично завершено с предупреждениями
- `error` - ошибка

#### errors[]
Массив структурированных ошибок (уже есть):
- `code`: string
- `message`: string
- `source_id`: string | null
- `platform`: string | null
- `context`: dict | null

## Действия

- [x] Добавить `error_message` в `by_source[]` при создании progress_entry
- [x] Обновить функцию `_mark_source()` для передачи error_message
- [x] Обновить вызовы `_mark_source()` в `_execute_scraping_job()`

## Реализовано

Поле `error_message` теперь включается в каждый элемент `by_source[]` при ошибках:

```json
{
  "source_id": "uuid-2",
  "platform": "instagram",
  "collected": 0,
  "status": "error",
  "error_code": "PLATFORM_PRIVATE",
  "error_message": "Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами (минимум 50 постов). Используйте /ingest/manual_posts для загрузки."
}
```

Бот может теперь просто обращаться к `source['error_message']` без необходимости искать ошибку в общем массиве `errors[]`.
