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
    AWAITING_BRIEF_CHOICE,  # Ask if user wants to do briefing now or later
    AWAITING_BRIEF_Q1_GOAL,
    AWAITING_BRIEF_Q2_AUDIENCE,
    AWAITING_BRIEF_Q3_TONE,
    AWAITING_BRIEF_Q4_TOPIC,
    AWAITING_BRIEF_Q5_FREQUENCY,
    # Branch 2: Beginners
    AWAITING_STYLESEED_TONE,
    AWAITING_STYLESEED_GOAL,
    AWAITING_STYLESEED_TOPIC,
    # Post-onboarding
    MAIN_MENU,
) = range(12)


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
        f"👋 Привет!\n"
        f"Я — твой ИИ-SMM агент. Помогу тебе:\n"
        f"• писать посты в твоём стиле,\n"
        f"• создавать визуалы и контент-планы,\n"
        f"• вовлекать аудиторию и продавать.\n\n"
        f"Выбери, что тебе ближе:"
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
            "📎 Пожалуйста, отправьте ссылки на ваши социальные сети: Instagram, Telegram, VK\n\n"
            "Примеры:\n\n"
            "Telegram → https://t.me/channel_name\n\n"
            "Instagram → https://instagram.com/username\n\n"
            "VK → https://vk.com/username\n\n"
            "Отправляйте по одной ссылке. Когда закончите, напишите 'готово'.\n\n"
            "🔒 Если аккаунт закрыт — откройте на время анализа."
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

    if text.lower() in ['готово', 'готов', 'done', 'готова']:
        sources_count = context.user_data.get('sources_count', 0)

        if sources_count < 1:
            await update.message.reply_text(
                "Вы ещё не добавили ни одной ссылки.\n"
                "Пожалуйста, отправьте хотя бы одну ссылку на ваши соцсети."
            )
            return AWAITING_SOURCES

        # User finished adding sources - ask about briefing
        total_posts = context.user_data.get('total_posts', 0)
        if total_posts < 50:
            await update.message.reply_text(
                f"⚠️ Собрано всего {total_posts} постов.\n"
                f"Рекомендуем добавить больше контента для точного анализа (точность может снизиться на ~15%)."
            )

        # Ask if user wants to do briefing now
        message = (
            "🧠 Хотите пройти брифинг сейчас?\n\n"
            "Это поможет мне лучше понять ваши цели и создавать более точный контент."
        )
        keyboard = [
            ["Да, пройти сейчас"],
            ["Позже"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(message, reply_markup=reply_markup)
        return AWAITING_BRIEF_CHOICE

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

        await update.message.reply_text("✅ Аккаунт сохранён!")

        # Start scraping content from the source
        await update.message.reply_text("📥 Начинаю сбор контента...")

        scrape_result = await api_client.scrape_source(
            source_id=result['id'],
            user_id=context.user_data['user_id'],
            access_token=context.user_data['access_token']
        )

        if not scrape_result or scrape_result.get('status') == 'ERROR':
            await update.message.reply_text(
                "😔 Произошла ошибка при сборе контента. Попробуйте добавить другой аккаунт."
            )
            return AWAITING_SOURCES

        posts_collected = scrape_result.get('posts_collected', 0)

        # Check if enough posts collected
        if posts_collected >= 50:
            # Track total posts collected
            if 'total_posts' not in context.user_data:
                context.user_data['total_posts'] = 0
            context.user_data['total_posts'] += posts_collected

            await update.message.reply_text(
                f"✅ Собрано {posts_collected} постов!\n\n"
                f"Отлично! Этого достаточно для анализа вашего стиля."
            )

            # Ask if user wants to do briefing now
            message = (
                "🧠 Хотите пройти брифинг сейчас?\n\n"
                "Это поможет мне лучше понять ваши цели и создавать более точный контент."
            )
            keyboard = [
                ["Да, пройти сейчас"],
                ["Позже"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(message, reply_markup=reply_markup)
            return AWAITING_BRIEF_CHOICE
        else:
            # Not enough posts
            await update.message.reply_text(
                f"⚠️ Собрано {posts_collected} постов (нужно минимум 50).\n\n"
                f"Добавьте ещё один аккаунт с большим количеством постов для точного анализа.\n\n"
                f"Или отправьте 'готово' если хотите продолжить с текущим количеством (точность может снизиться на ~15%)."
            )
            return AWAITING_SOURCES

    elif status == "CLOSED":
        await update.message.reply_text(
            "🔒 У вас закрытый аккаунт. Откройте временно или прикрепите файл с ≥50 постами."
        )
        return AWAITING_SOURCES

    elif status == "LOW_CONTENT":
        await update.message.reply_text(
            "⚠️ У аккаунта мало постов. Добавьте другие соцсети или файл — иначе точность анализа снизится (~−15%)."
        )
        return AWAITING_SOURCES

    elif status == "DUPLICATE":
        await update.message.reply_text(
            "Эта ссылка уже добавлена."
        )
        return AWAITING_SOURCES

    elif status == "INVALID_URL":
        await update.message.reply_text(
            "Не удалось распознать ссылку. Проверьте формат:\n"
            "https://t.me/... / https://vk.com/... / https://instagram.com/..."
        )
        return AWAITING_SOURCES

    else:
        await update.message.reply_text(
            "😔 Неизвестный статус проверки. Попробуйте ещё раз."
        )
        return AWAITING_SOURCES


async def handle_brief_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's choice about briefing"""
    choice = update.message.text

    if choice == "Да, пройти сейчас":
        # Start briefing
        message = (
            "Чтобы писать посты максимально точно под твои цели, ответь на пару вопросов 👇\n\n"
            "Вопрос 1️⃣ — Цель контента\n\n"
            "Что ты хочешь от своих соцсетей?\n"
            "💡 Привлекать клиентов\n"
            "🧠 Строить личный бренд\n"
            "📚 Делиться знаниями\n"
            "❤️ Вдохновлять людей\n"
            "💬 Общаться с аудиторией"
        )
        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return AWAITING_BRIEF_Q1_GOAL

    elif choice == "Позже":
        # Skip briefing for now, go to main menu
        context.user_data['brief_pending'] = True
        await update.message.reply_text(
            "Хорошо! Вы можете пройти брифинг позже из главного меню.\n\n"
            "Переходим в главное меню...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await show_main_menu(update, context)

    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из вариантов, используя кнопки."
        )
        return AWAITING_BRIEF_CHOICE


async def handle_brief_q1_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 1 - Goal"""
    context.user_data['brief_goal'] = update.message.text.strip()

    message = (
        "Вопрос 2️⃣ — Целевая аудитория\n\n"
        "Кому ты обычно пишешь?\n"
        "👩 Женская\n"
        "👨 Мужская\n"
        "👥 Смешанная\n"
        "👩‍💼 Предприниматели / специалисты\n"
        "🧘 Люди, ищущие вдохновение"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q2_AUDIENCE


async def handle_brief_q2_audience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 2 - Audience"""
    context.user_data['brief_audience'] = update.message.text.strip()

    message = (
        "Вопрос 3️⃣ — Тональность общения\n\n"
        "Какой стиль тебе ближе?\n"
        "🎯 Деловой\n"
        "💬 Дружелюбный\n"
        "🔥 Энергичный\n"
        "🧘 Спокойный\n"
        "😎 Ироничный"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q3_TONE


async def handle_brief_q3_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 3 - Tone"""
    context.user_data['brief_tone'] = update.message.text.strip()

    message = (
        "Вопрос 4️⃣ — Тематика / ниша\n\n"
        "О чём твой блог или бизнес?\n"
        "(Например: психология, нутрициология, маркетинг, коучинг, творчество и т.д.)"
    )
    await update.message.reply_text(message)
    return AWAITING_BRIEF_Q4_TOPIC


async def handle_brief_q4_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Brief Question 4 - Topic"""
    context.user_data['brief_topic'] = update.message.text.strip()

    message = (
        "Вопрос 5️⃣ — Частота публикаций\n\n"
        "Как часто хочешь публиковать посты?\n"
        "🔹 Ежедневно\n"
        "🔹 3 раза в неделю\n"
        "🔹 1 раз в неделю"
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

    # Brief/StyleSeed completed
    context.user_data['brief_pending'] = False
    context.user_data['onboarding_completed'] = True

    # Show completion message
    await update.message.reply_text(
        "🔥 Отлично! Теперь я понимаю, кто твоя аудитория и зачем ты создаёшь контент.\n"
        "Начинаю анализ твоего стиля — это займёт пару минут."
    )

    # Go to main menu
    return await show_main_menu(update, context)


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

    # Brief/StyleSeed completed
    context.user_data['brief_pending'] = False
    context.user_data['onboarding_completed'] = True

    # Show completion message
    await update.message.reply_text(
        "🔥 Отлично! Теперь я понимаю, кто твоя аудитория и зачем ты создаёшь контент.\n"
        "Начинаю анализ твоего стиля — это займёт пару минут."
    )

    # Go to main menu
    return await show_main_menu(update, context)


# ========== MAIN MENU ==========

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show main menu with available actions"""
    message = "📱 Главное меню\n\nВыберите действие:"

    keyboard = []

    # Check if briefing is pending
    if context.user_data.get('brief_pending', False):
        keyboard.append(["🧠 Пройти брифинг"])

    # Main menu options
    keyboard.append(["📝 Создать пост"])
    keyboard.append(["📅 Контент-план"])
    keyboard.append(["🎨 Настроить стиль"])
    keyboard.append(["ℹ️ Помощь"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(message, reply_markup=reply_markup)
    return MAIN_MENU


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu choices"""
    choice = update.message.text

    if choice == "🧠 Пройти брифинг":
        # Start briefing
        message = (
            "Чтобы писать посты максимально точно под твои цели, ответь на пару вопросов 👇\n\n"
            "Вопрос 1️⃣ — Цель контента\n\n"
            "Что ты хочешь от своих соцсетей?\n"
            "💡 Привлекать клиентов\n"
            "🧠 Строить личный бренд\n"
            "📚 Делиться знаниями\n"
            "❤️ Вдохновлять людей\n"
            "💬 Общаться с аудиторией"
        )
        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return AWAITING_BRIEF_Q1_GOAL

    elif choice == "📝 Создать пост":
        await update.message.reply_text(
            "🚧 Функция создания постов скоро будет доступна!"
        )
        return MAIN_MENU

    elif choice == "📅 Контент-план":
        await update.message.reply_text(
            "🚧 Функция контент-плана в разработке!"
        )
        return MAIN_MENU

    elif choice == "🎨 Настроить стиль":
        await update.message.reply_text(
            "🚧 Настройка стиля будет доступна в следующей версии!"
        )
        return MAIN_MENU

    elif choice == "ℹ️ Помощь":
        await help_command(update, context)
        return MAIN_MENU

    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из вариантов меню."
        )
        return MAIN_MENU


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
            AWAITING_BRIEF_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_choice)
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
            # Main menu
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)
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
