import logging
import re
import asyncio
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


# ========== SCRAPING JOB MONITORING (T6.1) ==========

async def monitor_scraping_job(
    application: Application,
    chat_id: int,
    job_id: str,
    user_id: str,
    access_token: str
):
    """
    Monitor scraping job status and notify user when complete (T6.1)

    Polls GET /ingest/status every 10 seconds until job is done.
    When complete, sends message with briefing offer.
    """
    logger.info(f"Starting job monitoring: job_id={job_id}, chat_id={chat_id}")

    poll_interval = 10  # seconds
    max_polls = 120  # 20 minutes max
    polls_count = 0

    while polls_count < max_polls:
        try:
            # Get job status
            status_data = await api_client.get_job_status(job_id, access_token)

            if not status_data:
                logger.error(f"Failed to get job status: job_id={job_id}")
                await application.bot.send_message(
                    chat_id=chat_id,
                    text="😔 Произошла ошибка при отслеживании сбора постов. Проверьте статус позже через меню."
                )
                return

            status = status_data.get('status')
            progress = status_data.get('progress', {})
            total_collected = progress.get('total_collected', 0)
            recommendations = status_data.get('recommendations', [])

            logger.info(f"Job {job_id} status: {status}, collected: {total_collected}")

            # Check if job is complete
            if status in ['done', 'partial', 'error']:
                # Send completion message
                if status == 'done':
                    message = f"✅ Отлично! Собрано {total_collected} постов.\n\n"
                elif status == 'partial':
                    message = f"⚠️ Частично завершено. Собрано {total_collected} постов.\n\n"
                else:  # error
                    message = f"❌ Не удалось собрать достаточно постов. Собрано: {total_collected}.\n\n"

                # Add recommendations if any
                if recommendations:
                    message += "💡 Рекомендации:\n"
                    for rec in recommendations:
                        message += f"• {rec}\n"
                    message += "\n"

                # T6.1: Offer briefing after scraping
                message += (
                    "🧠 Хочу точнее подстроиться под твои цели.\n"
                    "Ответишь на 5 вопросов? Это займёт ~1 минуту."
                )

                keyboard = [
                    ["🔧 Пройти сейчас"],
                    ["⏭️ Позже в настройках"]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

                await application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=reply_markup
                )

                logger.info(f"Job {job_id} monitoring complete. Status: {status}")
                return

            # Job still running, wait and check again
            polls_count += 1
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error monitoring job {job_id}: {e}")
            await asyncio.sleep(poll_interval)
            polls_count += 1

    # Timeout reached
    logger.warning(f"Job {job_id} monitoring timeout after {max_polls * poll_interval} seconds")
    await application.bot.send_message(
        chat_id=chat_id,
        text="⏱️ Сбор постов занимает больше времени, чем ожидалось. Проверьте статус позже через меню."
    )


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
    Step 1: Collect and verify social media sources (3-5 links) - T6.1 version
    Uses POST /sources/verify to check each URL
    Starts async scraping job when user types "готово"
    """
    text = update.message.text.strip()

    if text.lower() in ['готово', 'готов', 'done', 'готова']:
        # Initialize added_sources list if not exists
        if 'added_sources' not in context.user_data:
            context.user_data['added_sources'] = []

        sources_count = len(context.user_data.get('added_sources', []))

        if sources_count < 1:
            await update.message.reply_text(
                "Вы ещё не добавили ни одной ссылки.\n"
                "Пожалуйста, отправьте хотя бы одну ссылку на ваши соцсети."
            )
            return AWAITING_SOURCES

        # T6.1: Start async scraping job for all added sources
        await update.message.reply_text(
            f"📥 Отлично! Начинаю сбор постов из {sources_count} источников...\n\n"
            f"Это может занять несколько минут. Я уведомлю вас, когда всё будет готово."
        )

        # Start scraping job
        source_ids = context.user_data['added_sources']
        job_result = await api_client.start_scraping_job(
            user_id=context.user_data['user_id'],
            source_ids=source_ids,
            access_token=context.user_data['access_token'],
            target_posts=100,
            min_posts=50
        )

        if not job_result:
            await update.message.reply_text(
                "😔 Произошла ошибка при запуске сбора постов. Попробуйте позже."
            )
            return MAIN_MENU

        job_id = job_result.get('job_id')
        logger.info(f"Started scraping job: job_id={job_id}, sources={len(source_ids)}")

        # T6.1: Start background task to monitor job status
        asyncio.create_task(
            monitor_scraping_job(
                application=context.application,
                chat_id=update.effective_chat.id,
                job_id=job_id,
                user_id=context.user_data['user_id'],
                access_token=context.user_data['access_token']
            )
        )

        # Go to main menu immediately (monitoring runs in background)
        return MAIN_MENU

    # T6.1: Verify URL with API
    verification = await api_client.verify_source(
        url=text,
        access_token=context.user_data['access_token']
    )

    if not verification:
        await update.message.reply_text(
            "😔 Произошла ошибка при проверке ссылки. Попробуйте ещё раз."
        )
        return AWAITING_SOURCES

    # T6.1: Handle new response format
    accessible = verification.get('accessible', False)
    private = verification.get('private', False)
    post_count = verification.get('post_count', 0)
    handle = verification.get('handle', '')
    normalized_url = verification.get('normalized_url', text)
    message_text = verification.get('message', '')
    platform = api_client._detect_platform(text)

    # Check if source is accessible
    if not accessible:
        await update.message.reply_text(
            f"😔 {message_text}\n\n"
            f"Проверьте ссылку и попробуйте снова."
        )
        return AWAITING_SOURCES

    # Warn about private or low content
    if private:
        await update.message.reply_text(
            f"🔒 {message_text}"
        )
    elif post_count < 50:
        await update.message.reply_text(
            f"⚠️ {message_text}"
        )

    # Save source to database
    result = await api_client.create_source(
        user_id=context.user_data['user_id'],
        platform=platform,
        url=normalized_url,
        access_token=context.user_data['access_token']
    )

    if not result:
        await update.message.reply_text(
            "😔 Произошла ошибка при сохранении ссылки. Попробуйте ещё раз."
        )
        return AWAITING_SOURCES

    if result.get('error') == 'duplicate':
        await update.message.reply_text(
            "ℹ️ Этот источник уже добавлен ранее.\n\n"
            "Добавьте другую ссылку или напишите 'готово'."
        )
        return AWAITING_SOURCES

    # T6.1: Save source_id for later async scraping
    if 'added_sources' not in context.user_data:
        context.user_data['added_sources'] = []

    context.user_data['added_sources'].append(result['id'])
    sources_count = len(context.user_data['added_sources'])

    await update.message.reply_text(
        f"✅ Аккаунт сохранён! ({sources_count} источников добавлено)\n\n"
        f"Добавьте ещё ссылки или напишите 'готово' для начала сбора постов."
    )

    return AWAITING_SOURCES


async def handle_brief_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's choice about briefing (T6.1 compatible)"""
    choice = update.message.text

    # T6.1: New buttons from post-scraping offer
    if choice in ["Да, пройти сейчас", "🔧 Пройти сейчас"]:
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

    elif choice in ["Позже", "⏭️ Позже в настройках"]:
        # Skip briefing for now, go to main menu
        # T6.1: Create brief with completion=0
        try:
            brief_result = await api_client.create_brief(
                user_id=context.user_data['user_id'],
                goal="",
                audience="",
                tone="",
                topic="",
                frequency="",
                access_token=context.user_data['access_token'],
                completion=0  # T6.1: Mark as not completed
            )
            if brief_result:
                logger.info(f"Created placeholder brief with completion=0: {brief_result['id']}")
        except Exception as e:
            logger.error(f"Failed to create placeholder brief: {e}")

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
