# Руководство по настройке Telegram скрапера

## Обзор

Telegram скрапер использует **Telethon** (клиент user-bot) для скрапинга публичных каналов и групп. Он скачивает медиафайлы и загружает их в S3 для хранения.

## Предварительные требования

1. **API credentials Telegram** с https://my.telegram.org/apps
2. **AWS S3 bucket** для хранения медиа
3. **Telethon** и **boto3** установлены (уже в requirements.txt)

## Шаг 1: Получение API credentials Telegram

### 1.1 Перейдите на https://my.telegram.org/apps

### 1.2 Войдите с помощью номера телефона

### 1.3 Создайте новое приложение:
- **App title**: AI-SMM Scraper
- **Short name**: aismm
- **Platform**: Other
- **Description**: Content scraper for AI-SMM

### 1.4 Скопируйте ваши credentials:
- **api_id**: 12345678
- **api_hash**: abcdef1234567890abcdef1234567890

## Шаг 2: Настройка переменных окружения

Добавьте в `.env`:

```bash
# Telegram Scraper (Telethon)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_SESSION_NAME=aismm_scraper
```

## Шаг 3: Настройка AWS S3

### 3.1 Создайте S3 Bucket

```bash
aws s3 mb s3://aismm-media --region us-east-1
```

### 3.2 Настройте bucket policy для публичного доступа (опционально):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::aismm-media/*"
    }
  ]
}
```

### 3.3 Добавьте AWS credentials в `.env`:

```bash
# AWS S3 for Media Storage
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_S3_BUCKET=aismm-media
AWS_S3_REGION=us-east-1
```

## Шаг 4: Первый запуск (аутентификация сессии)

При первом запуске Telethon создаст файл сессии и может запросить верификацию по телефону:

```bash
# Запуск в Docker или локально
python -c "from scrapers.telegram import TelegramScraper; import asyncio; asyncio.run(TelegramScraper('https://t.me/channel').verify())"
```

**Вас могут попросить:**
1. Ввести номер телефона: `+1234567890`
2. Ввести код верификации: `12345`
3. Ввести пароль 2FA (если включен)

**Расположение файла сессии:**
- Сессия будет сохранена как `aismm_scraper.session`
- Этот файл содержит данные аутентификации и НЕ должен быть закоммичен в git
- Добавьте `*.session` в `.gitignore`

## Шаг 5: Проверка настройки

Протестируйте скрапер с публичным каналом:

```bash
curl -X POST http://localhost:8000/sources/verify \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "telegram",
    "url": "https://t.me/durov"
  }'
```

Ожидаемый ответ:
```json
{
  "handle": "@durov",
  "accessible": true,
  "private": false,
  "post_count": 150,
  "normalized_url": "https://t.me/durov",
  "message": "Channel verified: 150 posts",
  "recommendations": []
}
```

## Возможности

### ✅ Поддерживается

- **Публичные каналы** - скрапинг любого публичного Telegram канала
- **Текст сообщений** - полное содержимое постов
- **Фотографии** - скачивание и загрузка в S3
- **Видео** - скачивание (до 50МБ) и загрузка в S3
- **Метрики**:
  - Количество просмотров
  - Количество пересылок
  - Количество комментариев/ответов
- **Форматы URL**:
  - `https://t.me/channel`
  - `t.me/channel`
  - `@channel`
  - `channel`

### ❌ Не поддерживается (пока)

- Приватные каналы (требуется приглашение/доступ)
- Группы (можно легко добавить)
- Stories
- Опросы
- Большие видео (>50МБ) - пропускаются для избежания проблем с памятью

## Архитектура

```
┌──────────────────┐
│  TelegramScraper │
└────────┬─────────┘
         │
         ├─→ verify() ────→ Проверка доступности канала
         │                  Получение количества постов
         │                  Определение приватного статуса
         │
         └─→ scrape() ────→ Получение последних N сообщений (по умолчанию: 200)
                            │
                            ├─→ Скачивание фотографий ──→ Загрузка в S3
                            ├─→ Скачивание видео ──→ Загрузка в S3
                            │
                            └─→ Возврат нормализованных постов
```

## Хранение медиа

Медиафайлы хранятся в S3 со следующей структурой:

```
s3://aismm-media/
  └── telegram/
      └── channel_name/
          ├── abc123.jpg    (фото)
          ├── def456.jpg    (фото)
          └── xyz789.mp4    (видео)
```

**Именование файлов:**
- Случайный UUID для предотвращения коллизий
- Оригинальное расширение файла сохраняется
- Content-Type определяется автоматически

## Ограничения скорости

Telegram имеет ограничения скорости для API запросов:

- **Верификация**: ~30 запросов/минуту
- **Получение сообщений**: ~20 запросов/минуту
- **Скачивание медиа**: Зависит от размера файла

**Лучшие практики:**
- Добавляйте задержки между запросами
- Используйте батч-операции когда возможно
- Обрабатывайте `FloodWaitError` с экспоненциальной задержкой

## Обработка ошибок

Скрапер обрабатывает распространенные ошибки:

| Ошибка | Описание | Действие |
|--------|----------|----------|
| `ChannelPrivateError` | Канал приватный | Возврат статуса `CLOSED` |
| `ChannelInvalidError` | Канал не существует | Возврат статуса `INVALID_URL` |
| `UsernameNotOccupiedError` | Имя пользователя не найдено | Возврат статуса `INVALID_URL` |
| `FloodWaitError` | Превышен лимит скорости | Ожидание и повтор |

Все ошибки логируются только с типом ошибки (безопасность: нет PII в логах).

## Безопасность

### ✅ Безопасно

- **Логи**: Только типы ошибок, никаких URL или контента
- **Файл сессии**: Зашифрован Telethon
- **S3 URLs**: Хранятся как `s3://...`, а не HTTPS
- **Поле Raw**: Пустое `{}` (нет полных данных сообщения)

### ⚠️ Важно

- **НЕ** коммитьте файлы `.session`
- **НЕ** логируйте полные сообщения об ошибках (могут содержать URL)
- **НЕ** храните хендлы пользователей в логах (PII)

Добавьте в `.gitignore`:
```
*.session
*.session-journal
```

## Устранение неполадок

### Проблема: "Telegram API credentials not configured"

**Решение**: Проверьте, что в файле `.env` есть `TELEGRAM_API_ID` и `TELEGRAM_API_HASH`

### Проблема: "Channel is private or unavailable"

**Решение**:
1. Проверьте, является ли канал публичным
2. Убедитесь, что у вас есть доступ к каналу
3. Попробуйте с другим каналом (например, `@durov`)

### Проблема: "AWS credentials not configured"

**Решение**:
1. Создайте AWS IAM пользователя с доступом к S3
2. Добавьте credentials в `.env`
3. Протестируйте с помощью: `aws s3 ls s3://aismm-media/`

### Проблема: "FloodWaitError: A wait of X seconds is required"

**Решение**:
- Telegram ограничивает скорость ваших запросов
- Подождите X секунд перед повторной попыткой
- Уменьшите частоту скрапинга

### Проблема: "Session file permission denied"

**Решение**:
```bash
chmod 600 *.session
```

## Тестирование

### Тест верификации:

```python
from scrapers.telegram import TelegramScraper
import asyncio

async def test():
    scraper = TelegramScraper("https://t.me/durov")
    result = await scraper.verify()
    print(result)

asyncio.run(test())
```

### Тест скрапинга:

```python
from scrapers.telegram import TelegramScraper
import asyncio

async def test():
    scraper = TelegramScraper("https://t.me/durov")
    posts = await scraper.scrape(limit=10)
    print(f"Скраплено {len(posts)} постов")
    for post in posts[:3]:
        print(f"- {post['text'][:50]}...")

asyncio.run(test())
```

## Чеклист для продакшена

- [ ] Telegram API credentials настроены
- [ ] AWS S3 bucket создан и настроен
- [ ] Файлы `.session` в `.gitignore`
- [ ] Файл сессии создан (аутентификация при первом запуске)
- [ ] Протестировано с публичным каналом
- [ ] Обработка ошибок проверена
- [ ] Лимиты скорости настроены
- [ ] Настроен мониторинг/логирование
- [ ] Резервная копия файла сессии (зашифрована)

## Ресурсы

- Документация Telethon: https://docs.telethon.dev/
- Telegram API: https://my.telegram.org/apps
- Документация AWS S3: https://docs.aws.amazon.com/s3/
