#!/bin/bash
# Универсальный скрипт очистки базы данных
# Автоматически определяет креденшалы из .env

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🗑️  Утилита очистки базы данных${NC}"
echo ""

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo "Создайте .env файл на основе .env.example"
    exit 1
fi

# Загружаем переменные из .env
export $(cat .env | grep -v '^#' | xargs)

# Определяем креденшалы
DB_USER="${POSTGRES_USER:-aismm}"
DB_NAME="${POSTGRES_DB:-aismm}"

echo -e "${BLUE}Настройки подключения:${NC}"
echo "  Пользователь: $DB_USER"
echo "  База данных: $DB_NAME"
echo ""

# Проверяем, что Docker запущен
if ! docker-compose ps | grep -q "postgres"; then
    echo -e "${RED}❌ Контейнер PostgreSQL не запущен!${NC}"
    echo "Запустите: docker-compose up -d"
    exit 1
fi

echo -e "${YELLOW}⚠️  ВНИМАНИЕ! Будут удалены следующие данные:${NC}"
echo "  • Все задания скрапинга"
echo "  • Все посты"
echo "  • Все источники"
echo "  • Все стилевые профили"
echo "  • Все брифы"
echo "  • Все style seeds"
echo ""
echo -e "${GREEN}✓ Пользователи будут СОХРАНЕНЫ${NC}"
echo ""

# Подтверждение
read -p "Продолжить? (yes/no): " confirm

if [ "$confirm" != "yes" ] && [ "$confirm" != "y" ]; then
    echo -e "${RED}❌ Операция отменена${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}📊 Статистика ДО очистки:${NC}"

# Показываем статистику ДО
docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs
UNION ALL SELECT 'briefs', COUNT(*) FROM briefs
UNION ALL SELECT 'style_profiles', COUNT(*) FROM style_profiles
UNION ALL SELECT 'style_seed', COUNT(*) FROM style_seed;
EOF

echo ""
echo -e "${YELLOW}🔧 Удаляем данные...${NC}"

# Выполняем очистку
docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
DELETE FROM scraping_jobs;
DELETE FROM posts;
DELETE FROM sources;
DELETE FROM style_profiles;
DELETE FROM briefs;
DELETE FROM style_seed;
EOF

echo -e "${GREEN}  ✓ Данные удалены${NC}"

echo ""
echo -e "${BLUE}📊 Статистика ПОСЛЕ очистки:${NC}"

# Показываем статистику ПОСЛЕ
docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs
UNION ALL SELECT 'briefs', COUNT(*) FROM briefs
UNION ALL SELECT 'style_profiles', COUNT(*) FROM style_profiles
UNION ALL SELECT 'style_seed', COUNT(*) FROM style_seed;
EOF

echo ""
echo -e "${GREEN}✅ Очистка успешно завершена!${NC}"
