#!/bin/bash
# Wrapper для запуска очистки базы данных через Docker

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🗑️  Утилита очистки базы данных${NC}"
echo ""

# Проверяем, что Docker запущен
if ! docker-compose ps | grep -q "api"; then
    echo -e "${RED}❌ Контейнер API не запущен!${NC}"
    echo "Запустите: docker-compose up -d"
    exit 1
fi

# Передаем все аргументы в контейнер
docker-compose exec -T api python -m api.utils.clear_database "$@"
