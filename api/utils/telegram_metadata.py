"""Utilities for extracting metadata from Telegram messages"""

import re
from typing import List, Dict, Any
from telethon.tl.types import (
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityTextUrl,
    MessageEntityUrl,
    MessageEntityHashtag,
    MessageEntityBold,
    MessageEntityItalic,
    MessageEntityCode,
    MessageEntityPre,
    MessageEntityEmail,
    MessageEntityPhone,
    Message
)


def extract_hashtags(text: str) -> List[str]:
    """
    Extract all hashtags from text

    Args:
        text: Message text

    Returns:
        List of hashtags without # symbol

    Example:
        "Check out #python and #coding tips"
        -> ["python", "coding"]
    """
    if not text:
        return []

    # Find all hashtags (# followed by letters, numbers, underscores)
    hashtags = re.findall(r'#(\w+)', text)
    return list(set(hashtags))  # Remove duplicates


def extract_mentions(text: str) -> List[str]:
    """
    Extract all @mentions from text

    Args:
        text: Message text

    Returns:
        List of mentions without @ symbol

    Example:
        "Thanks @user1 and @channel"
        -> ["user1", "channel"]
    """
    if not text:
        return []

    # Find all mentions (@ followed by letters, numbers, underscores)
    mentions = re.findall(r'@(\w+)', text)
    return list(set(mentions))  # Remove duplicates


def extract_urls(text: str) -> List[str]:
    """
    Extract all URLs from text

    Args:
        text: Message text

    Returns:
        List of URLs

    Example:
        "Visit https://example.com and http://test.org"
        -> ["https://example.com", "http://test.org"]
    """
    if not text:
        return []

    # Find all URLs (http/https)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return urls


def extract_entities_metadata(message: Message) -> Dict[str, Any]:
    """
    Extract rich metadata from Telegram message entities

    Telegram provides structured entities for:
    - Hashtags
    - Mentions
    - URLs (including text URLs)
    - Formatting (bold, italic, code)
    - Email, phone numbers

    Args:
        message: Telethon Message object

    Returns:
        Dictionary with extracted metadata

    Example:
        {
            "hashtags": ["python", "coding"],
            "mentions": ["user1", "channel"],
            "urls": ["https://example.com"],
            "emails": ["test@example.com"],
            "phones": ["+1234567890"],
            "formatting": {
                "has_bold": true,
                "has_italic": false,
                "has_code": true
            }
        }
    """
    metadata = {
        "hashtags": [],
        "mentions": [],
        "urls": [],
        "emails": [],
        "phones": [],
        "formatting": {
            "has_bold": False,
            "has_italic": False,
            "has_code": False,
            "has_pre": False
        }
    }

    if not message.entities:
        # Fallback to regex extraction if no entities
        if message.message:
            metadata["hashtags"] = extract_hashtags(message.message)
            metadata["mentions"] = extract_mentions(message.message)
            metadata["urls"] = extract_urls(message.message)
        return metadata

    text = message.message or ""

    for entity in message.entities:
        # Extract text for this entity
        entity_text = text[entity.offset:entity.offset + entity.length]

        # Hashtags
        if isinstance(entity, MessageEntityHashtag):
            hashtag = entity_text.lstrip('#')
            if hashtag:
                metadata["hashtags"].append(hashtag)

        # Mentions
        elif isinstance(entity, (MessageEntityMention, MessageEntityMentionName)):
            mention = entity_text.lstrip('@')
            if mention:
                metadata["mentions"].append(mention)

        # URLs
        elif isinstance(entity, MessageEntityUrl):
            if entity_text:
                metadata["urls"].append(entity_text)

        # Text URLs (links with custom text)
        elif isinstance(entity, MessageEntityTextUrl):
            if entity.url:
                metadata["urls"].append(entity.url)

        # Email
        elif isinstance(entity, MessageEntityEmail):
            if entity_text:
                metadata["emails"].append(entity_text)

        # Phone
        elif isinstance(entity, MessageEntityPhone):
            if entity_text:
                metadata["phones"].append(entity_text)

        # Formatting
        elif isinstance(entity, MessageEntityBold):
            metadata["formatting"]["has_bold"] = True
        elif isinstance(entity, MessageEntityItalic):
            metadata["formatting"]["has_italic"] = True
        elif isinstance(entity, MessageEntityCode):
            metadata["formatting"]["has_code"] = True
        elif isinstance(entity, MessageEntityPre):
            metadata["formatting"]["has_pre"] = True

    # Remove duplicates
    metadata["hashtags"] = list(set(metadata["hashtags"]))
    metadata["mentions"] = list(set(metadata["mentions"]))
    metadata["urls"] = list(set(metadata["urls"]))
    metadata["emails"] = list(set(metadata["emails"]))
    metadata["phones"] = list(set(metadata["phones"]))

    return metadata


def extract_reactions(message: Message) -> Dict[str, int]:
    """
    Extract emoji reactions from message

    Args:
        message: Telethon Message object

    Returns:
        Dictionary with emoji -> count mapping

    Example:
        {
            "❤": 150,
            "👍": 89,
            "🔥": 45
        }
    """
    reactions = {}

    if not message.reactions or not message.reactions.results:
        return reactions

    for reaction_count in message.reactions.results:
        # Get emoji
        if hasattr(reaction_count.reaction, 'emoticon'):
            emoji = reaction_count.reaction.emoticon
            count = reaction_count.count
            reactions[emoji] = count

    return reactions


def get_post_metadata(message: Message) -> Dict[str, Any]:
    """
    Extract complete metadata from Telegram message

    Combines all metadata extraction functions into one.

    Args:
        message: Telethon Message object

    Returns:
        Complete metadata dictionary

    Example:
        {
            "hashtags": ["python", "coding"],
            "mentions": ["user1"],
            "urls": ["https://example.com"],
            "emails": [],
            "phones": [],
            "reactions": {"❤": 150, "👍": 89},
            "formatting": {"has_bold": true, ...},
            "is_pinned": false,
            "is_edited": false,
            "edit_date": null
        }
    """
    # Get entities metadata
    metadata = extract_entities_metadata(message)

    # Add reactions
    metadata["reactions_emoji"] = extract_reactions(message)

    # Add message properties
    metadata["is_pinned"] = message.pinned if hasattr(message, 'pinned') else False
    metadata["is_edited"] = bool(message.edit_date)
    metadata["edit_date"] = message.edit_date.isoformat() if message.edit_date else None

    # Add view/forward/reply counts for convenience
    metadata["views"] = message.views or 0
    metadata["forwards"] = message.forwards or 0
    metadata["replies"] = message.replies.replies if message.replies else 0

    return metadata
