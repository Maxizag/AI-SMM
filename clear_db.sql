-- Скрипт для очистки базы данных
-- Использование:
-- docker-compose exec postgres psql -U ai_smm_user -d ai_smm_db -f /clear_db.sql

\echo '🗑️  Начинаем очистку базы данных...'
\echo ''

-- Показываем статистику ДО очистки
\echo '📊 Статистика ДО очистки:'
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs
UNION ALL SELECT 'briefs', COUNT(*) FROM briefs
UNION ALL SELECT 'style_profiles', COUNT(*) FROM style_profiles
UNION ALL SELECT 'style_seed', COUNT(*) FROM style_seed;

\echo ''
\echo '🔧 Удаляем данные...'

-- Удаляем данные (CASCADE удалит связанные записи)
DELETE FROM scraping_jobs;
\echo '  ✓ Задания скрапинга удалены'

DELETE FROM posts;
\echo '  ✓ Посты удалены'

DELETE FROM sources;
\echo '  ✓ Источники удалены'

DELETE FROM style_profiles;
\echo '  ✓ Стилевые профили удалены'

DELETE FROM briefs;
\echo '  ✓ Брифы удалены'

DELETE FROM style_seed;
\echo '  ✓ Style seeds удалены'

-- Раскомментируйте следующую строку, если нужно удалить и пользователей
-- DELETE FROM users;
-- \echo '  ✓ Пользователи удалены'

\echo ''
\echo '📊 Статистика ПОСЛЕ очистки:'
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'sources', COUNT(*) FROM sources
UNION ALL SELECT 'posts', COUNT(*) FROM posts
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs
UNION ALL SELECT 'briefs', COUNT(*) FROM briefs
UNION ALL SELECT 'style_profiles', COUNT(*) FROM style_profiles
UNION ALL SELECT 'style_seed', COUNT(*) FROM style_seed;

\echo ''
\echo '✅ Очистка завершена!'
