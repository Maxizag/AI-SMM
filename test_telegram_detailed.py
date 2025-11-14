#!/usr/bin/env python3
"""
Enhanced test script - saves full scraped data to JSON file

Usage:
    python test_telegram_detailed.py <channel_url> [limit]

Example:
    python test_telegram_detailed.py https://t.me/durov 5
    python test_telegram_detailed.py @your_channel 10
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from scrapers.telegram import TelegramScraper


async def scrape_and_save(channel_url: str, limit: int = 10):
    """
    Scrape channel and save full data to JSON file

    Args:
        channel_url: Channel URL or handle
        limit: Number of posts to scrape
    """
    print(f"🚀 Scraping {channel_url}")
    print(f"Fetching {limit} posts...")
    print("=" * 60)

    try:
        scraper = TelegramScraper(channel_url)
        posts = await scraper.scrape(limit=limit)

        print(f"\n✅ Scraped {len(posts)} posts\n")

        # Display summary
        for i, post in enumerate(posts, 1):
            print(f"--- Post {i} ---")
            print(f"  ID: {post['platform_post_id']}")
            print(f"  Date: {post['posted_at']}")
            print(f"  Views: {post['reactions']['views']:,}")
            print(f"  Forwards: {post['reactions']['forwards']:,}")

            # Show full text (first 200 chars in console, full in file)
            text = post['text']
            if len(text) > 200:
                print(f"  Text: {text[:200]}...")
                print(f"       (Full text: {len(text)} characters - see JSON file)")
            else:
                print(f"  Text: {text}")

            print(f"  Media: {len(post['media'])} items")
            print(f"  Link: {post['link']}")
            print()

        # Save to JSON file
        handle = scraper.handle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_{handle}_{timestamp}.json"

        # Get absolute path
        abs_path = os.path.abspath(filename)

        # Convert datetime objects to strings for JSON
        posts_serializable = []
        for post in posts:
            post_copy = post.copy()
            if post_copy['posted_at']:
                post_copy['posted_at'] = post_copy['posted_at'].isoformat()
            posts_serializable.append(post_copy)

        # Save with pretty formatting
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'channel': handle,
                'scraped_at': datetime.now().isoformat(),
                'total_posts': len(posts_serializable),
                'posts': posts_serializable
            }, f, ensure_ascii=False, indent=2)

        print("=" * 60)
        print(f"📄 Full data saved to:")
        print(f"   {abs_path}")
        print(f"\n   Total posts: {len(posts)}")
        print(f"   Total characters: {sum(len(p['text']) for p in posts):,}")
        print(f"\nOpen with: cat {filename}")
        print(f"Or:        open {filename}")
        print("\nFull post texts are in this file!")

        return posts

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def show_stats(posts):
    """Show statistics about scraped posts"""
    if not posts:
        return

    print("\n" + "=" * 60)
    print("📊 STATISTICS")
    print("=" * 60)

    total_views = sum(p['reactions']['views'] for p in posts)
    total_forwards = sum(p['reactions']['forwards'] for p in posts)
    total_chars = sum(len(p['text']) for p in posts)

    print(f"Total posts: {len(posts)}")
    print(f"Total views: {total_views:,}")
    print(f"Total forwards: {total_forwards:,}")
    print(f"Total characters: {total_chars:,}")
    print(f"Average views per post: {total_views // len(posts):,}")
    print(f"Average text length: {total_chars // len(posts)} characters")

    # Find most popular post
    most_viewed = max(posts, key=lambda p: p['reactions']['views'])
    print(f"\nMost viewed post:")
    print(f"  Views: {most_viewed['reactions']['views']:,}")
    print(f"  Link: {most_viewed['link']}")
    print(f"  Text: {most_viewed['text'][:100]}...")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_telegram_detailed.py <channel_url> [limit]")
        print("\nExamples:")
        print("  python test_telegram_detailed.py https://t.me/durov 5")
        print("  python test_telegram_detailed.py @your_channel 10")
        sys.exit(1)

    channel_url = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    async def run():
        posts = await scrape_and_save(channel_url, limit)
        if posts:
            await show_stats(posts)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
