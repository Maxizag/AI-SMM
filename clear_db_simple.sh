#!/bin/bash
# Простая очистка базы данных через SQL

echo "🗑️  Очистка базы данных через SQL..."
echo ""
echo "⚠️  ВНИМАНИЕ! Будут удалены все данные кроме пользователей!"
echo ""
read -p "Продолжить? (yes/no): " confirm

if [ "$confirm" != "yes" ] && [ "$confirm" != "y" ]; then
    echo "❌ Операция отменена"
    exit 0
fi

# Копируем SQL-скрипт в контейнер и выполняем
docker cp clear_db.sql $(docker-compose ps -q postgres):/clear_db.sql
docker-compose exec -T postgres psql -U ai_smm_user -d ai_smm_db -f /clear_db.sql

echo ""
echo "✅ Готово!"
