# Текущий статус проекта (19.11.2025)

## ✅ Что работает:
1. **Telegram scraper подключается к API** через StringSession
2. **Скачивает посты и медиа** (логи показывают "Fetched 45 messages", "Saved media to...")
3. **Локальное хранилище медиа** работает (отключили S3)
4. **Docker контейнеры** запускаются корректно
5. **Бот** работает, добавление источников запускается

## ❌ Что НЕ работает:
1. **Посты не сохраняются в БД** - Error saving post: DBAPIError (need full traceback)
2. **Дубликаты источников** - UniqueViolationError при повторном добавлении
3. **Счётчик total_collected = 0** хотя посты скачались

## 🔧 Что нужно исправить:

### Приоритет 1: Сохранение постов в БД
Файлы: `api/services/scraping_service.py`, `api/tasks/scraping_tasks.py`
Проблема: После INSERT в таблицу posts происходит ROLLBACK с DBAPIError
Нужно: Добавить полный traceback ошибки и исправить

### Приоритет 2: Обработка дубликатов источников  
Файл: `api/routers/onboarding.py` (или где добавляются sources)
Проблема: UniqueViolationError на constraint "uniq_user_url"
Решение: Добавить проверку или ON CONFLICT DO NOTHING

## 📝 Важные детали:

### Telegram аутентификация:
- Используется **StringSession** из переменной `TELEGRAM_STRING_SESSION` в .env
- НЕ используется файл telegram_session.session
- Метод `_init_client` в `api/scrapers/telegram.py` правильно настроен
- Используется `client.connect()` вместо `client.start()` (для Docker)

### Структура БД (таблица posts):
- Есть constraint: `ix_posts_source_platform_post UNIQUE (source_id, platform_post_id)`
- Поля: id, user_id, source_id, platform, platform_post_id, author_handle, posted_at, **text** (не content!), media, reactions, link, lang, qdrant_point_id, raw, created_at

### Конфигурация:
- AWS S3 закомментирован в .env
- Используется локальное хранилище: `/app/media/`
- SQLALCHEMY_ECHO=true для дебага
- LOG_LEVEL=DEBUG

## 🎯 Следующие шаги:
1. Добавить полный traceback в логи при ошибке сохранения поста
2. Исправить DBAPIError при INSERT в posts
3. Добавить обработку дубликатов источников
4. Проверить что счётчик total_collected обновляется

## 🌿 Git ветки:
- **claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb** ← РАБОЧАЯ ВЕТКА (здесь все исправления)
- claude/ai-smm-agency-setup-011CUkxwusUsyebzem8vPrfS (старая, проблемная)
- origin/claude/initial-setup-01GA7hkbfbGpDE8ubihVmr7g (самая старая)

**ВАЖНО:** Работать только в ветке `claude/continue-session-011CUzHNUa4B43Dsx28X3Jjb`!
