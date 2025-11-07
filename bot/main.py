import logging
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
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

# FSM States
(
    AWAITING_USER_TYPE,
    # Branch 1: Experienced users
    AWAITING_SOURCES,
    AWAITING_BRIEF_Q1_GOAL,
    AWAITING_BRIEF_Q2_AUDIENCE,
    AWAITING_BRIEF_Q3_TONE,
    AWAITING_BRIEF_Q4_TOPIC,
    AWAITING_BRIEF_Q5_FREQUENCY,
    # Branch 2: Beginners
    AWAITING_STYLESEED_TONE,
    AWAITING_STYLESEED_GOAL,
    AWAITING_STYLESEED_TOPIC,
    # Analysis
    ANALYSIS_RUNNING,
) = range(11)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for /start command
    Shows welcome message and choice buttons
    """
    user = update.effective_user

    if not user:
        await update.message.reply_text("Ошибка: не удалось получить данные пользователя.")
        return ConversationHandler.END

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
        return ConversationHandler.END

    # Save user data in context
    context.user_data['user_id'] = auth_data['user']['id']
    context.user_data['access_token'] = auth_data['access_token']
    context.user_data['tg_user_id'] = user.id

    logger.info(f"User {user.id} authenticated. User ID: {auth_data['user']['id']}")

    # Welcome message with choice buttons
    welcome_message = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я — ИИ-SMM Агент, ваш помощник в создании контента.\n\n"
        f"🎯 Я помогу вам:\n"
        f"• Генерировать посты в вашем стиле\n"
        f"• Создавать контент-планы\n"
        f"• Адаптировать тон и формат под вашу аудиторию\n\n"
        f"Давайте начнём! Выберите подходящий вариант:"
    )

    # Keyboard with two choice buttons
    keyboard = [
        ["У меня уже есть соцсети"],
        ["Я только начинаю"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    return AWAITING_USER_TYPE


async def handle_user_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's choice of onboarding branch"""
    choice = update.message.text

    if choice == "У меня уже есть соцсети":
        # Branch 1: Experienced users
        context.user_data['verified_sources'] = []
        context.user_data['sources_count'] = 0

        message = (
            "Отлично! 🎉\n\n"
            "Для качественной генерации контента мне нужно изучить ваш стиль.\n\n"
            "📎 Пожалуйста, отправьте ссылки на ваши социальные сети (от 3 до 5 ссылок):\n"
            "• Instagram, Telegram, VK, Twitter и т.д.\n\n"
            "Примеры:\n"
            "• https://instagram.com/username\n"
            "• https://t.me/channel_name\n\n"
            "Отправляйте по одной ссылке. Когда закончите, напишите 'готово'."
        )

        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return AWAITING_SOURCES

    elif choice == "Я только начинаю":
        # Branch 2: Beginners
        message = (
            "Замечательно! Начнём с нуля 🌱\n\n"
            "Я задам вам несколько вопросов, чтобы понять какой контент вам нужен.\n\n"
            "❓ Вопрос 1/3:\n\n"
            "Какой тон общения вы предпочитаете?\n\n"
            "Примеры:\n"
            "• Дружелюбный и casual\n"
            "• Профессиональный и строгий\n"
            "• Мотивирующий и энергичный\n"
            "• Экспертный и информативный"
        )

        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return AWAITING_STYLESEED_TONE

    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из предложенных вариантов, используя кнопки."
        )
        return AWAITING_USER_TYPE


# ========== BRANCH 1: EXPERIENCED USERS ==========

async def handle_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Step 1: Collect and verify social media sources (3-5 links)
    Uses POST /sources/verify to check each URL
    """
    text = update.message.text.strip()

    if text.lower() == 'готово':
        sources_count = context.user_data.get('sources_count', 0)

        if sources_count < 3:
            await update.message.reply_text(
                f"Вы добавили только {sources_count} ссылки.\n"
                f"Пожалуйста, добавьте ещё {3 - sources_count} ссылки для лучшего анализа."
            )
            return AWAITING_SOURCES

        # Move to brief questions (Step 2)
        message = (
            f"Отлично! Я сохранил {sources_count} источников. ✅\n\n"
            f"Теперь несколько вопросов о вашем контенте:\n\n"
            f"❓ Вопрос 1/5:\n\n"
            f"Какая цель вашего контента?\n\n"
            f"Примеры:\n"
            f"• Увеличить вовлеченность аудитории\n"
            f"• Привлечь новых клиентов\n"
            f"• Образовательный контент\n"
            f"• Продвижение личного бренда"
        )
        await update.message.reply_text(message)
        return AWAITING_BRIEF_Q1_GOAL

    # Verify URL with API
    verification = await api_client.verify_source(
        user_id=context.user_data['user_id'],
        url=text,
        access_token=context.user_data['access_token']
    )

    if not verification:
        await update.message.reply_text(
            "😔 Произошла ошибка при проверке ссылки. Попробуйте ещё раз."
        )
        return AWAITING_SOURCES

    status = verification.get('status')

    # Handle different verification statuses
    if status == "OK":
        # Extract platform from URL
        platform = "unknown"
        url_lower = text.lower()
        if "instagram.com" in url_lower or "instagr.am" in url_lower:
            platform = "instagram"
        elif "t.me" in url_lower or "telegram.org" in url_lower:
            platform = "telegram"
        elif "vk.com" in url_lower:
            platform = "vk"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            platform = "twitter"
        elif "facebook.com" in url_lower or "fb.com" in url_lower:
            platform = "facebook"
        elif "tiktok.com" in url_lower:
            platform = "tiktok"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            platform = "youtube"

        # Save source to database
        result = await api_client.create_source(
            user_id=context.user_data['user_id'],
            platform=platform,
            url=text,
            access_token=context.user_data['access_token']
        )

        if not result:
            await update.message.reply_text(
                "😔 Произошла ошибка при сохранении ссылки. Попробуйте ещё раз."
            )
            return AWAITING_SOURCES

        # Track verified sources
        if 'verified_sources' not in context.user_data:
            context.user_data['verified_sources'] = []
        context.user_data['verified_sources'].append(result)
        context.user_data['sources_count'] = len(context.user_data['verified_sources'])

        sources_count = context.user_data['sources_count']
        posts_count = verification.get('posts_count', 0)

        if sources_count >= 5:
            # Max reached, move to brief
            message = (
                f"✅ Аккаунт сохранён! (найдено {posts_count} постов)\n\n"
                f"Отлично! Я сохранил {sources_count} источников (максимум). ✅\n\n"
                f"Теперь несколько вопросов о вашем контенте:\n\n"
                f"❓ Вопрос 1/5:\n\n"
                f"Какая цель вашего контента?\n\n"
                f"Примеры:\n"
                f"• Увеличить вовлеченность аудитории\n"
                f"• Привлечь новых клиентов\n"
                f"• Образовательный контент\n"
                f"• Продвижение личного бренда"
            )
            await update.message.reply_text(message)
            return AWAITING_BRIEF_Q1_GOAL

        await update.message.reply_text(
            f"✅ Аккаунт сохранён! (найдено {posts_count} постов)\n\n"
            f"Добавлено источников: {sources_count}/5\n\n"
            f"Отправьте следующую ссылку или напишите 'готово', если закончили (минимум 3 ссылки)."
        )
        return AWAITING_SOURCES

    elif status == "CLOSED":
        message = verification.get('message', "У вас закрытый аккаунт.")
        await update.message.reply_text(
            f"🔒 {message}\n\n"
            f"Пожалуйста, отправьте ссылку на открытый аккаунт или сделайте текущий публичным."
        )
        return AWAITING_SOURCES

    elif status == "LOW_CONTENT":
        message = verification.get('message', "В этом аккаунте мало контента.")
        posts_count = verification.get('posts_count', 0)
        await update.message.reply_text(
            f"📉 {message}\n\n"
            f"Найдено постов: {posts_count}\n"
            f"Для качественного анализа нужно минимум 50 постов.\n\n"
            f"Попробуйте добавить другой аккаунт с большим количеством контента."
        )
        return AWAITING_SOURCES

    elif status == "DUPLICATE":
        message = verification.get('message', "Вы уже добавили эту ссылку.")
        await update.message.reply_text(
            f"🔄 {message}\n\n"
            f"Пожалуйста, отправьте другую ссылку."
        )
        return AWAITING_SOURCES

    elif status == "INVALID_URL":
        message = verification.get('message', "Неверный формат ссылки.")
        await update.message.reply_text(
            f"❌ {message}\n\n"
            f"Пожалуйста, отправьте корректную ссылку в формате:\n"
            f"https://instagram.com/username"
        )
        return AWAITING_SOURCES

    else:
        await update.message.reply_text(
            "😔 Неизвестный статус проверки. Попробуйте ещё раз."
        )
        return AWAITING_SOURCES


async def handle_brief_q1_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 1 - Goal"""
    context.user_data['brief_goal'] = update.message.text.strip()

    message = (
        "❓ Вопрос 2/5:\n\n"
        "Кто ваша целевая аудитория?\n\n"
        "Примеры:\n"
        "• IT-специалисты 25-35 лет\n"
        "• Предприниматели и владельцы бизнеса\n"
        "• Молодые родители\n"
        "• Студенты и начинающие специалисты"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q2_AUDIENCE


async def handle_brief_q2_audience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 2 - Audience"""
    context.user_data['brief_audience'] = update.message.text.strip()

    message = (
        "❓ Вопрос 3/5:\n\n"
        "Какой тон общения предпочитаете?\n\n"
        "Примеры:\n"
        "• Профессиональный, но дружелюбный\n"
        "• Строгий и деловой\n"
        "• Casual и неформальный\n"
        "• Мотивирующий и вдохновляющий"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q3_TONE


async def handle_brief_q3_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 3 - Tone"""
    context.user_data['brief_tone'] = update.message.text.strip()

    message = (
        "❓ Вопрос 4/5:\n\n"
        "Какая основная тема/ниша вашего контента?\n\n"
        "Примеры:\n"
        "• Искусственный интеллект и технологии\n"
        "• Здоровье и фитнес\n"
        "• Бизнес и предпринимательство\n"
        "• Образование и саморазвитие"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q4_TOPIC


async def handle_brief_q4_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 4 - Topic"""
    context.user_data['brief_topic'] = update.message.text.strip()

    message = (
        "❓ Вопрос 5/5 (последний!):\n\n"
        "Как часто вы планируете публиковать контент?\n\n"
        "Примеры:\n"
        "• Каждый день\n"
        "• 3 раза в неделю\n"
        "• 2-3 раза в неделю\n"
        "• 1 раз в неделю"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q5_FREQUENCY


async def handle_brief_q5_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 5 - Frequency and save to API"""
    context.user_data['brief_frequency'] = update.message.text.strip()

    # Save brief via API
    result = await api_client.create_brief(
        user_id=context.user_data['user_id'],
        goal=context.user_data['brief_goal'],
        audience=context.user_data['brief_audience'],
        tone=context.user_data['brief_tone'],
        topic=context.user_data['brief_topic'],
        frequency=context.user_data['brief_frequency'],
        access_token=context.user_data['access_token']
    )

    if not result:
        await update.message.reply_text(
            "😔 Произошла ошибка при сохранении брифа. Пожалуйста, попробуйте /start снова."
        )
        return ConversationHandler.END

    # Show analysis message
    await update.message.reply_text(
        "✅ Спасибо! Все данные сохранены.\n\n"
        "Начинаю анализ твоего стиля — это займёт пару минут. 🔥"
    )

    return ANALYSIS_RUNNING


# ========== BRANCH 2: BEGINNERS ==========

async def handle_styleseed_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect StyleSeed: Tone"""
    context.user_data['styleseed_tone'] = update.message.text.strip()

    message = (
        "❓ Вопрос 2/3:\n\n"
        "Какая цель вашего контента?\n\n"
        "Примеры:\n"
        "• Набрать первую 1000 подписчиков\n"
        "• Найти первых клиентов\n"
        "• Делиться знаниями и опытом\n"
        "• Построить личный бренд"
    )
    await update.message.reply_text(message)
    return AWAITING_STYLESEED_GOAL


async def handle_styleseed_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect StyleSeed: Goal"""
    context.user_data['styleseed_goal'] = update.message.text.strip()

    message = (
        "❓ Вопрос 3/3 (последний!):\n\n"
        "О чём вы хотите писать? Выберите тему:\n\n"
        "Примеры:\n"
        "• Технологии и стартапы\n"
        "• Маркетинг и продажи\n"
        "• Дизайн и креатив\n"
        "• Здоровье и ЗОЖ"
    )
    await update.message.reply_text(message)
    return AWAITING_STYLESEED_TOPIC


async def handle_styleseed_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect StyleSeed: Topic and save to API"""
    context.user_data['styleseed_topic'] = update.message.text.strip()

    # Save style seed via API
    result = await api_client.create_style_seed(
        user_id=context.user_data['user_id'],
        tone=context.user_data['styleseed_tone'],
        goal=context.user_data['styleseed_goal'],
        topic=context.user_data['styleseed_topic'],
        access_token=context.user_data['access_token']
    )

    if not result:
        await update.message.reply_text(
            "😔 Произошла ошибка при сохранении данных. Пожалуйста, попробуйте /start снова."
        )
        return ConversationHandler.END

    # Show analysis message
    await update.message.reply_text(
        "✅ Спасибо! Все данные сохранены.\n\n"
        "Начинаю анализ твоего стиля — это займёт пару минут. 🔥"
    )

    return ANALYSIS_RUNNING


# ========== ANALYSIS STATE ==========

async def handle_analysis_running(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle messages during analysis"""
    await update.message.reply_text(
        "⏳ Анализ всё ещё выполняется...\n\n"
        "Пожалуйста, подождите немного. Я уведомлю вас, когда всё будет готово!"
    )
    return ANALYSIS_RUNNING


# ========== UTILITY HANDLERS ==========

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation"""
    await update.message.reply_text(
        "Онбординг отменён. Напишите /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /help command"""
    help_text = (
        "🤖 *Доступные команды:*\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/cancel - Отменить текущий процесс\n\n"
        "📝 *Как использовать бота:*\n\n"
        "1. Пройдите онбординг (/start)\n"
        "2. Выберите свой уровень опыта\n"
        "3. Ответьте на вопросы\n"
        "4. Получите персонализированный контент\n\n"
        "Если у вас есть вопросы, просто напишите!"
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

    # Conversation handler for onboarding
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            AWAITING_USER_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_type_choice)
            ],
            # Branch 1: Experienced users
            AWAITING_SOURCES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sources)
            ],
            AWAITING_BRIEF_Q1_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_q1_goal)
            ],
            AWAITING_BRIEF_Q2_AUDIENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_q2_audience)
            ],
            AWAITING_BRIEF_Q3_TONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_q3_tone)
            ],
            AWAITING_BRIEF_Q4_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_q4_topic)
            ],
            AWAITING_BRIEF_Q5_FREQUENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_q5_frequency)
            ],
            # Branch 2: Beginners
            AWAITING_STYLESEED_TONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_styleseed_tone)
            ],
            AWAITING_STYLESEED_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_styleseed_goal)
            ],
            AWAITING_STYLESEED_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_styleseed_topic)
            ],
            # Analysis
            ANALYSIS_RUNNING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_analysis_running)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))

    # Start bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
