"""Error codes and messages for scraping operations"""

from enum import Enum
from typing import Dict


class ScrapingErrorCode(str, Enum):
    """Error codes for scraping operations"""

    # Source-level errors
    PLATFORM_PRIVATE = "PLATFORM_PRIVATE"
    PLATFORM_INVALID_URL = "PLATFORM_INVALID_URL"
    PLATFORM_NOT_FOUND = "PLATFORM_NOT_FOUND"
    PLATFORM_INSUFFICIENT_CONTENT = "PLATFORM_INSUFFICIENT_CONTENT"
    PLATFORM_ACCESS_DENIED = "PLATFORM_ACCESS_DENIED"
    PLATFORM_RATE_LIMIT = "PLATFORM_RATE_LIMIT"
    PLATFORM_UNAVAILABLE = "PLATFORM_UNAVAILABLE"

    # Job-level errors
    JOB_INSUFFICIENT_POSTS = "JOB_INSUFFICIENT_POSTS"
    JOB_NO_SOURCES = "JOB_NO_SOURCES"
    JOB_ALL_SOURCES_FAILED = "JOB_ALL_SOURCES_FAILED"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Actionable error messages for users
ERROR_MESSAGES: Dict[ScrapingErrorCode, str] = {
    ScrapingErrorCode.PLATFORM_PRIVATE: (
        "Аккаунт закрыт. Откройте профиль на время или загрузите файл с постами "
        "(минимум 50 постов). Используйте /ingest/manual_posts для загрузки."
    ),

    ScrapingErrorCode.PLATFORM_INVALID_URL: (
        "Неверный формат ссылки. Проверьте URL и попробуйте снова."
    ),

    ScrapingErrorCode.PLATFORM_NOT_FOUND: (
        "Аккаунт не найден. Убедитесь, что ссылка правильная и аккаунт существует."
    ),

    ScrapingErrorCode.PLATFORM_INSUFFICIENT_CONTENT: (
        "В источнике недостаточно постов (меньше 50). Добавьте ещё ссылку или "
        "загрузите архив постов через /ingest/manual_posts."
    ),

    ScrapingErrorCode.PLATFORM_ACCESS_DENIED: (
        "Доступ к источнику ограничен. Проверьте, что аккаунт публичный или "
        "предоставьте доступ для скрапинга."
    ),

    ScrapingErrorCode.PLATFORM_RATE_LIMIT: (
        "Превышен лимит запросов к платформе. Попробуйте через 15-30 минут."
    ),

    ScrapingErrorCode.PLATFORM_UNAVAILABLE: (
        "Платформа временно недоступна. Попробуйте позже."
    ),

    ScrapingErrorCode.JOB_INSUFFICIENT_POSTS: (
        "Собрано недостаточно постов для качественного анализа стиля. "
        "Рекомендации:\n"
        "• Добавьте ещё 1-2 источника\n"
        "• Загрузите архив постов через /ingest/manual_posts\n"
        "• Укажите референсы для вдохновения через /ingest/hints\n\n"
        "Минимум 50 постов требуется для хорошего качества стиля."
    ),

    ScrapingErrorCode.JOB_NO_SOURCES: (
        "Нет источников для скрапинга. Добавьте хотя бы один источник через "
        "/sources/v2."
    ),

    ScrapingErrorCode.JOB_ALL_SOURCES_FAILED: (
        "Не удалось собрать посты ни из одного источника. Проверьте доступность "
        "источников и попробуйте снова."
    ),

    ScrapingErrorCode.INTERNAL_ERROR: (
        "Внутренняя ошибка системы. Попробуйте позже или обратитесь в поддержку."
    ),
}


def get_error_message(code: ScrapingErrorCode, **context) -> str:
    """
    Get user-facing error message for error code

    Args:
        code: Error code
        **context: Additional context for message formatting

    Returns:
        User-friendly error message with actionable guidance
    """
    message = ERROR_MESSAGES.get(code, ERROR_MESSAGES[ScrapingErrorCode.INTERNAL_ERROR])

    # Format with context if provided
    try:
        return message.format(**context)
    except KeyError:
        return message


def create_error_object(
    code: ScrapingErrorCode,
    source_id: str = None,
    platform: str = None,
    **context
) -> Dict:
    """
    Create structured error object for API responses

    Args:
        code: Error code
        source_id: Optional source ID where error occurred
        platform: Optional platform name
        **context: Additional context

    Returns:
        Structured error object with code, message, and metadata
    """
    error = {
        "code": code.value,
        "message": get_error_message(code, **context),
    }

    if source_id:
        error["source_id"] = source_id

    if platform:
        error["platform"] = platform

    if context:
        error["context"] = context

    return error
