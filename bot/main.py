import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import get_settings
from api_client import APIClient

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Initialize API client
api_client = APIClient(settings.api_base_url)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for /start command

    Steps:
    1. Get Telegram user data
    2. Authenticate with API (POST /auth/tg)
    3. Save user_id in context
    4. Send welcome message
    """
    user = update.effective_user

    if not user:
        await update.message.reply_text("Ошибка: не удалось получить данные пользователя.")
        return

    logger.info(f"User started bot: {user.id} (@{user.username}) - {user.full_name}")

    # Authenticate with API
    auth_data = await api_client.authenticate_telegram_user(
        tg_user_id=user.id,
        name=user.full_name or user.first_name or "User",
        username=user.username
    )

    if not auth_data:
        await update.message.reply_text(
            "😔 Извините, произошла ошибка при регистрации. "
            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        return

    # Save user data in context
    context.user_data['user_id'] = auth_data['user']['id']
    context.user_data['access_token'] = auth_data['access_token']
    context.user_data['tg_user_id'] = user.id

    # Send welcome message
    welcome_message = (
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        f"Я — ИИ-SMM Агент, ваш помощник в создании контента.\n\n"
        f"Я помогу вам:\n"
        f"• 📝 Писать посты в вашем уникальном стиле\n"
        f"• 🎨 Генерировать идеи для контента\n"
        f"• 📊 Анализировать эффективность постов\n\n"
        f"Для начала работы мне нужно изучить ваш стиль написания. "
        f"Пожалуйста, отправьте мне несколько ваших постов или текстов, "
        f"которые вы обычно публикуете в социальных сетях.\n\n"
        f"Чем больше примеров вы предоставите, тем точнее я смогу имитировать ваш стиль! 🚀"
    )

    await update.message.reply_text(welcome_message)

    logger.info(f"User {user.id} successfully authenticated. User ID: {auth_data['user']['id']}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /help command"""
    help_text = (
        "🤖 *Доступные команды:*\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n\n"
        "📝 *Как использовать бота:*\n\n"
        "1. Отправьте мне свои посты для анализа стиля\n"
        "2. Попросите создать новый пост\n"
        "3. Получите контент в вашем уникальном стиле\n\n"
        "Если у вас есть вопросы, просто напишите мне!"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def post_init(application: Application) -> None:
    """Post-initialization hook"""
    logger.info("Bot initialized successfully")


async def post_shutdown(application: Application) -> None:
    """Post-shutdown hook"""
    logger.info("Shutting down bot...")
    await api_client.close()


def main() -> None:
    """Start the bot"""
    logger.info("Starting AI-SMM Telegram Bot...")

    if not settings.telegram_bot_token or settings.telegram_bot_token == "...":
        logger.error("TELEGRAM_BOT_TOKEN is not set or invalid!")
        logger.error("Please set TELEGRAM_BOT_TOKEN in .env file")
        return

    # Create application
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Start bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
