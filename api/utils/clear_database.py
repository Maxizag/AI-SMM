"""
Утилита для очистки всех данных из базы данных

Использование:
    python -m api.utils.clear_database

Опции:
    --all          - Удалить все данные включая пользователей
    --keep-users   - Удалить только контент, оставить пользователей (по умолчанию)
    --user-id      - Удалить данные конкретного пользователя
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import text
from api.database import AsyncSessionLocal, engine
from api.models import User, Source, Post, StyleProfile, Brief, StyleSeed, ScrapingJob


async def clear_all_data():
    """Полностью очищает все данные из базы, включая пользователей"""
    async with AsyncSessionLocal() as session:
        try:
            print("🗑️  Очистка всех данных из базы данных...")

            # Из-за CASCADE при удалении пользователей удалятся и связанные данные
            await session.execute(text("DELETE FROM scraping_jobs"))
            await session.execute(text("DELETE FROM posts"))
            await session.execute(text("DELETE FROM sources"))
            await session.execute(text("DELETE FROM style_profiles"))
            await session.execute(text("DELETE FROM briefs"))
            await session.execute(text("DELETE FROM style_seed"))
            await session.execute(text("DELETE FROM users"))

            await session.commit()
            print("✅ Все данные успешно удалены!")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при очистке данных: {e}")
            raise


async def clear_content_only():
    """Очищает только контент, оставляя пользователей"""
    async with AsyncSessionLocal() as session:
        try:
            print("🗑️  Очистка контента (посты, источники, задания)...")

            await session.execute(text("DELETE FROM scraping_jobs"))
            print("  ✓ Задания скрапинга удалены")

            await session.execute(text("DELETE FROM posts"))
            print("  ✓ Посты удалены")

            await session.execute(text("DELETE FROM sources"))
            print("  ✓ Источники удалены")

            await session.execute(text("DELETE FROM style_profiles"))
            print("  ✓ Стилевые профили удалены")

            await session.execute(text("DELETE FROM briefs"))
            print("  ✓ Брифы удалены")

            await session.execute(text("DELETE FROM style_seed"))
            print("  ✓ Style seeds удалены")

            await session.commit()
            print("✅ Контент успешно очищен! Пользователи сохранены.")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при очистке контента: {e}")
            raise


async def clear_user_data(user_id: str):
    """Очищает данные конкретного пользователя"""
    async with AsyncSessionLocal() as session:
        try:
            print(f"🗑️  Очистка данных пользователя {user_id}...")

            # Проверяем существование пользователя
            result = await session.execute(
                text("SELECT name FROM users WHERE id = :user_id"),
                {"user_id": user_id}
            )
            user = result.first()

            if not user:
                print(f"❌ Пользователь с ID {user_id} не найден!")
                return

            print(f"  Пользователь: {user[0]}")

            # Удаляем данные пользователя
            await session.execute(
                text("DELETE FROM scraping_jobs WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            await session.execute(
                text("DELETE FROM posts WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            await session.execute(
                text("DELETE FROM sources WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            await session.execute(
                text("DELETE FROM style_profiles WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            await session.execute(
                text("DELETE FROM briefs WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            await session.execute(
                text("DELETE FROM style_seed WHERE user_id = :user_id"),
                {"user_id": user_id}
            )

            await session.commit()
            print(f"✅ Данные пользователя {user_id} успешно удалены!")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при очистке данных пользователя: {e}")
            raise


async def show_statistics():
    """Показывает статистику по данным в базе"""
    async with AsyncSessionLocal() as session:
        try:
            print("\n📊 Статистика базы данных:")
            print("=" * 50)

            # Пользователи
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            users_count = result.scalar()
            print(f"👥 Пользователи: {users_count}")

            # Источники
            result = await session.execute(text("SELECT COUNT(*) FROM sources"))
            sources_count = result.scalar()
            print(f"📡 Источники: {sources_count}")

            # Посты
            result = await session.execute(text("SELECT COUNT(*) FROM posts"))
            posts_count = result.scalar()
            print(f"📝 Посты: {posts_count}")

            # Задания скрапинга
            result = await session.execute(text("SELECT COUNT(*) FROM scraping_jobs"))
            jobs_count = result.scalar()
            print(f"⚙️  Задания скрапинга: {jobs_count}")

            # Брифы
            result = await session.execute(text("SELECT COUNT(*) FROM briefs"))
            briefs_count = result.scalar()
            print(f"📋 Брифы: {briefs_count}")

            # Style profiles
            result = await session.execute(text("SELECT COUNT(*) FROM style_profiles"))
            profiles_count = result.scalar()
            print(f"🎨 Стилевые профили: {profiles_count}")

            print("=" * 50)

        except Exception as e:
            print(f"❌ Ошибка при получении статистики: {e}")
            raise


async def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description="Утилита для очистки базы данных")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Удалить все данные включая пользователей"
    )
    parser.add_argument(
        "--keep-users",
        action="store_true",
        default=True,
        help="Удалить только контент, оставить пользователей (по умолчанию)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Удалить данные конкретного пользователя"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Показать только статистику без удаления"
    )

    args = parser.parse_args()

    # Показываем статистику ДО очистки
    await show_statistics()

    if args.stats:
        return

    # Подтверждение
    print("\n⚠️  ВНИМАНИЕ! Это действие нельзя отменить!")

    if args.all:
        print("Будут удалены ВСЕ данные включая пользователей!")
    elif args.user_id:
        print(f"Будут удалены данные пользователя {args.user_id}")
    else:
        print("Будут удалены посты, источники, задания (пользователи останутся)")

    confirm = input("\nПродолжить? (yes/no): ")

    if confirm.lower() not in ['yes', 'y', 'да', 'д']:
        print("❌ Операция отменена")
        return

    # Выполняем очистку
    if args.user_id:
        await clear_user_data(args.user_id)
    elif args.all:
        await clear_all_data()
    else:
        await clear_content_only()

    # Показываем статистику ПОСЛЕ очистки
    await show_statistics()


if __name__ == "__main__":
    asyncio.run(main())
