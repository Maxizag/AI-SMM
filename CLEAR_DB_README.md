# 🗑️ Быстрая очистка базы данных

## Самый простой способ (рекомендуется)

```bash
./clear_db_simple.sh
```

Скрипт спросит подтверждение и удалит все данные, кроме пользователей.

---

## Другие способы

### 1. Через Docker с Python (больше опций)

```bash
# Статистика БД
./clear_db.sh --stats

# Очистить все кроме пользователей
./clear_db.sh --keep-users

# Полная очистка (включая пользователей)
./clear_db.sh --all

# Очистить данные конкретного пользователя
./clear_db.sh --user-id "UUID"
```

### 2. Прямо через SQL

```bash
docker-compose exec -T postgres psql -U ai_smm_user -d ai_smm_db << 'EOF'
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
-- DELETE FROM users;  -- раскомментировать для удаления пользователей
EOF
```

### 3. Интерактивный SQL

```bash
docker-compose exec postgres psql -U ai_smm_user -d ai_smm_db
```

Затем выполните SQL команды:
```sql
-- Посмотреть статистику
SELECT 'users' as table, COUNT(*) FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs;

-- Очистить данные
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
-- DELETE FROM users;  -- если нужно удалить пользователей
```

---

## Ошибка "ModuleNotFoundError: No module named 'sqlalchemy'"?

Это значит, что вы пытаетесь запустить Python-скрипт локально без установленных зависимостей.

**Решение 1:** Используйте скрипты через Docker (они работают из коробки):
```bash
./clear_db_simple.sh
# или
./clear_db.sh --keep-users
```

**Решение 2:** Установите зависимости локально:
```bash
pip install -r api/requirements.txt
python -m api.utils.clear_database --keep-users
```

---

## Полная документация

См. [TESTING_GUIDE.md](./TESTING_GUIDE.md) для подробных инструкций.
