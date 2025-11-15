# Telegram Session Setup

Для работы Telegram scraper необходимо создать сессию Telethon.

## Быстрый старт

### 1. Получить Telegram API credentials

1. Перейди на https://my.telegram.org/apps
2. Войди со своим номером телефона
3. Создай приложение (если еще не создано)
4. Скопируй `api_id` и `api_hash`

### 2. Добавить credentials в .env

Добавь в `.env` файл:

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_SESSION_NAME=aismm_scraper
```

### 3. Установить зависимости

```bash
pip install telethon python-dotenv
```

### 4. Создать сессию

```bash
python create_telegram_session.py
```

Скрипт:
1. Попросит ввести номер телефона
2. Отправит код в Telegram
3. Попросит ввести код из Telegram
4. Создаст файл `aismm_scraper.session` в корне проекта

### 5. Проверить что сессия создана

```bash
ls -la aismm_scraper.session
```

Должен появиться файл `aismm_scraper.session`.

### 6. Запустить Docker

Теперь Docker контейнеры будут использовать созданную сессию:

```bash
cd infra
docker compose up -d
```

## Устранение проблем

### Ошибка "Please enter your phone (or bot token)"

Это значит что файл сессии не найден или не смонтирован в контейнер. Проверь:

1. Файл `aismm_scraper.session` существует в корне проекта
2. Docker compose правильно монтирует файл (смотри `volumes` в `docker-compose.yml`)

### Ошибка "Session is not authorized"

Сессия устарела или была отозвана. Нужно:

1. Удалить старый файл: `rm aismm_scraper.session`
2. Создать новую сессию: `python create_telegram_session.py`

### Файл сессии случайно закоммичен в git

```bash
# Удалить из git но оставить локально
git rm --cached aismm_scraper.session

# Убедиться что *.session в .gitignore
grep "*.session" .gitignore
```

## Безопасность

⚠️ **ВАЖНО:**
- Файл `.session` содержит токены авторизации
- **Никогда** не коммить `.session` файлы в git
- Файл уже добавлен в `.gitignore`
- Не делись файлом сессии с другими людьми

## Использование в продакшене

Для продакшена рекомендуется:

1. Создать отдельный Telegram аккаунт для scraper
2. Использовать секретное хранилище (AWS Secrets Manager, HashiCorp Vault)
3. Монтировать сессию через секретные volumes в Kubernetes/Docker Swarm
