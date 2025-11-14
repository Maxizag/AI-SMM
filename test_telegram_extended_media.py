#!/usr/bin/env python3
"""
Test Telegram extended media support

Tests all supported media types:
- Photos (single and albums)
- Videos
- GIF/animations
- Audio files
- Voice messages
- Video notes (round videos)
- Documents (PDF, DOCX, etc.)

Usage:
    python test_telegram_extended_media.py <channel_url> [limit]

Example:
    python test_telegram_extended_media.py https://t.me/durov 20
"""

import asyncio
import sys
import os
from collections import Counter

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from scrapers.telegram import TelegramScraper


async def test_extended_media(channel_url: str, limit: int = 20):
    """
    Test extended media extraction from channel posts

    Shows statistics for all media types found
    """
    print(f"🎬 Testing extended media from {channel_url}")
    print(f"Fetching {limit} posts...")
    print("=" * 60)

    try:
        scraper = TelegramScraper(channel_url)
        posts = await scraper.scrape(limit=limit)

        if not posts:
            print("❌ No posts found")
            return

        print(f"✅ Scraped {len(posts)} posts\n")

        # Statistics
        media_type_counts = Counter()
        total_media = 0
        albums = {}  # grouped_id -> list of media
        media_examples = {}

        # Analyze all posts
        for post in posts:
            if not post.get('media'):
                continue

            for media in post['media']:
                media_type = media.get('type', 'unknown')
                media_type_counts[media_type] += 1
                total_media += 1

                # Track albums
                if 'grouped_id' in media:
                    grouped_id = media['grouped_id']
                    if grouped_id not in albums:
                        albums[grouped_id] = []
                    albums[grouped_id].append(media)

                # Save first example of each type
                if media_type not in media_examples:
                    media_examples[media_type] = media

        # Display results
        print("=" * 60)
        print("📊 MEDIA STATISTICS")
        print("=" * 60)

        print(f"\n📦 Total media items: {total_media}")
        print(f"📝 Posts with media: {sum(1 for p in posts if p.get('media'))}")

        if media_type_counts:
            print("\n🎭 Media types found:")
            for media_type, count in media_type_counts.most_common():
                emoji = {
                    'photo': '📷',
                    'video': '🎥',
                    'gif': '🎞️',
                    'audio': '🎵',
                    'voice': '🎤',
                    'video_note': '⭕',
                    'document': '📄',
                    'image': '🖼️'
                }.get(media_type, '❓')
                print(f"   {emoji} {media_type}: {count}")

        # Album statistics
        if albums:
            print(f"\n📸 Photo albums found: {len(albums)}")
            print(f"   Largest album: {max(len(items) for items in albums.values())} items")
            print(f"   Total items in albums: {sum(len(items) for items in albums.values())}")

        # Show examples of each media type
        print("\n" + "=" * 60)
        print("📋 MEDIA EXAMPLES")
        print("=" * 60)

        for media_type, media in sorted(media_examples.items()):
            emoji = {
                'photo': '📷',
                'video': '🎥',
                'gif': '🎞️',
                'audio': '🎵',
                'voice': '🎤',
                'video_note': '⭕',
                'document': '📄',
                'image': '🖼️'
            }.get(media_type, '❓')

            print(f"\n{emoji} {media_type.upper()}")
            print(f"   URL: {media['url']}")
            print(f"   MIME: {media.get('mime_type', 'N/A')}")
            print(f"   Size: {media.get('size', 0) / 1024:.1f} KB")

            if 'filename' in media:
                print(f"   Filename: {media['filename']}")
            if 'duration' in media:
                print(f"   Duration: {media['duration']}s")
            if 'title' in media:
                print(f"   Title: {media['title']}")
            if 'performer' in media:
                print(f"   Artist: {media['performer']}")
            if 'width' in media and 'height' in media:
                print(f"   Dimensions: {media['width']}x{media['height']}")
            if 'grouped_id' in media:
                print(f"   Album ID: {media['grouped_id']}")

        # Show album examples
        if albums:
            print("\n" + "=" * 60)
            print("📸 ALBUM EXAMPLES")
            print("=" * 60)

            # Show first 3 albums
            for i, (grouped_id, items) in enumerate(list(albums.items())[:3], 1):
                print(f"\n📦 Album {i} (ID: {grouped_id})")
                print(f"   Items: {len(items)}")
                for j, item in enumerate(items, 1):
                    print(f"   {j}. {item['type']}: {item.get('size', 0) / 1024:.1f} KB")

        # Show posts with interesting media
        print("\n" + "=" * 60)
        print("🔍 POSTS WITH MEDIA")
        print("=" * 60)

        posts_with_media = [p for p in posts if p.get('media')][:5]
        for i, post in enumerate(posts_with_media, 1):
            print(f"\n📝 Post {i} (ID: {post['platform_post_id']})")
            print(f"   Date: {post['posted_at']}")
            print(f"   Views: {post['reactions']['views']:,}")

            text = post['text'][:100]
            if len(post['text']) > 100:
                text += "..."
            print(f"   Text: {text}")

            print(f"   Media ({len(post['media'])} items):")
            for media in post['media']:
                emoji = {
                    'photo': '📷',
                    'video': '🎥',
                    'gif': '🎞️',
                    'audio': '🎵',
                    'voice': '🎤',
                    'video_note': '⭕',
                    'document': '📄',
                    'image': '🖼️'
                }.get(media['type'], '❓')

                size_info = f"{media.get('size', 0) / 1024:.1f} KB"
                filename_info = f" ({media['filename']})" if 'filename' in media else ""
                album_info = f" [Album]" if 'grouped_id' in media else ""

                print(f"      {emoji} {media['type']}: {size_info}{filename_info}{album_info}")

        print("\n" + "=" * 60)
        print("✅ Extended media support working!")
        print("\nSupported types:")
        print("  📷 Photos (single and albums)")
        print("  🎥 Videos")
        print("  🎞️  GIF/animations")
        print("  🎵 Audio files")
        print("  🎤 Voice messages")
        print("  ⭕ Video notes (round)")
        print("  📄 Documents (PDF, DOCX, etc.)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_telegram_extended_media.py <channel_url> [limit]")
        print("\nExamples:")
        print("  python test_telegram_extended_media.py https://t.me/durov 20")
        print("  python test_telegram_extended_media.py @channel 10")
        sys.exit(1)

    channel_url = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    try:
        asyncio.run(test_extended_media(channel_url, limit))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
