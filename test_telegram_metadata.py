#!/usr/bin/env python3
"""
Test Telegram metadata extraction - hashtags, mentions, reactions

Usage:
    python test_telegram_metadata.py <channel_url> [limit]

Example:
    python test_telegram_metadata.py https://t.me/durov 10
"""

import asyncio
import sys
import os
from collections import Counter

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from scrapers.telegram import TelegramScraper


async def test_metadata(channel_url: str, limit: int = 10):
    """
    Test metadata extraction from channel posts

    Shows:
    - Hashtags extracted from posts
    - Mentions (@username references)
    - Emoji reactions with counts
    - URLs found in messages
    - Formatting (bold, italic, code)
    """
    print(f"🔍 Testing metadata extraction from {channel_url}")
    print(f"Fetching {limit} posts...")
    print("=" * 60)

    try:
        scraper = TelegramScraper(channel_url)
        posts = await scraper.scrape(limit=limit)

        if not posts:
            print("❌ No posts found")
            return

        print(f"✅ Scraped {len(posts)} posts\n")

        # Aggregate metadata across all posts
        all_hashtags = []
        all_mentions = []
        all_reactions = Counter()
        all_urls = []
        posts_with_bold = 0
        posts_with_italic = 0
        posts_with_code = 0

        # Display individual posts
        for i, post in enumerate(posts, 1):
            print(f"📝 Post {i} (ID: {post['platform_post_id']})")
            print(f"   Date: {post['posted_at']}")
            print(f"   Views: {post['reactions']['views']:,}")

            # Text preview
            text = post['text'][:150]
            if len(post['text']) > 150:
                text += "..."
            print(f"   Text: {text}\n")

            # Hashtags
            if post.get('hashtags'):
                print(f"   🏷️  Hashtags: {', '.join('#' + h for h in post['hashtags'])}")
                all_hashtags.extend(post['hashtags'])

            # Mentions
            if post.get('mentions'):
                print(f"   👤 Mentions: {', '.join('@' + m for m in post['mentions'])}")
                all_mentions.extend(post['mentions'])

            # URLs
            if post.get('urls'):
                print(f"   🔗 URLs: {len(post['urls'])} links")
                all_urls.extend(post['urls'])

            # Emoji reactions
            if post.get('reactions_emoji'):
                reaction_str = ", ".join(
                    f"{emoji} {count}"
                    for emoji, count in post['reactions_emoji'].items()
                )
                print(f"   ❤️  Reactions: {reaction_str}")
                all_reactions.update(post['reactions_emoji'])

            # Formatting
            formatting = post.get('formatting', {})
            if formatting.get('has_bold'):
                posts_with_bold += 1
            if formatting.get('has_italic'):
                posts_with_italic += 1
            if formatting.get('has_code'):
                posts_with_code += 1

            # Other metadata
            if post.get('is_pinned'):
                print(f"   📌 Pinned post")
            if post.get('is_edited'):
                print(f"   ✏️  Edited on {post.get('edit_date')}")

            print()

        # Summary statistics
        print("=" * 60)
        print("📊 METADATA SUMMARY")
        print("=" * 60)

        # Most common hashtags
        if all_hashtags:
            hashtag_counts = Counter(all_hashtags)
            print(f"\n🏷️  Top Hashtags:")
            for hashtag, count in hashtag_counts.most_common(5):
                print(f"   #{hashtag}: {count} times")
        else:
            print("\n🏷️  No hashtags found")

        # Most common mentions
        if all_mentions:
            mention_counts = Counter(all_mentions)
            print(f"\n👤 Top Mentions:")
            for mention, count in mention_counts.most_common(5):
                print(f"   @{mention}: {count} times")
        else:
            print("\n👤 No mentions found")

        # Emoji reactions
        if all_reactions:
            print(f"\n❤️  Emoji Reactions:")
            for emoji, count in all_reactions.most_common(10):
                print(f"   {emoji}: {count:,} total")
        else:
            print("\n❤️  No reactions found")

        # URLs
        if all_urls:
            print(f"\n🔗 URLs found: {len(all_urls)} total")
            # Show first 3
            for url in all_urls[:3]:
                print(f"   {url}")
            if len(all_urls) > 3:
                print(f"   ... and {len(all_urls) - 3} more")
        else:
            print("\n🔗 No URLs found")

        # Formatting stats
        print(f"\n✨ Formatting:")
        print(f"   Posts with bold: {posts_with_bold}")
        print(f"   Posts with italic: {posts_with_italic}")
        print(f"   Posts with code: {posts_with_code}")

        print("\n" + "=" * 60)
        print("✅ Metadata extraction working!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_telegram_metadata.py <channel_url> [limit]")
        print("\nExamples:")
        print("  python test_telegram_metadata.py https://t.me/durov 10")
        print("  python test_telegram_metadata.py @channel 5")
        sys.exit(1)

    channel_url = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    try:
        asyncio.run(test_metadata(channel_url, limit))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
