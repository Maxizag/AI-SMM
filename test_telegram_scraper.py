#!/usr/bin/env python3
"""
Test script for Telegram scraper

Usage:
    python test_telegram_scraper.py

This script will:
1. Test verify() on a public channel
2. Test scrape() to fetch posts
3. Display results
"""

import asyncio
import sys
import os

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from scrapers.telegram import TelegramScraper
from config import get_settings


async def test_verify():
    """Test channel verification"""
    print("=" * 60)
    print("TEST 1: Verify Telegram Channel")
    print("=" * 60)

    # Test with Durov's channel (public channel)
    test_url = "https://t.me/durov"
    print(f"\nTesting with: {test_url}")

    try:
        scraper = TelegramScraper(test_url)
        result = await scraper.verify()

        print("\n✅ Verification Result:")
        print(f"  Status: {result['status']}")
        print(f"  Handle: {result['handle']}")
        print(f"  Private: {result['is_private']}")
        print(f"  Post Count: {result['posts_count']}")
        print(f"  Message: {result['message']}")

        return result['status'] == 'OK'
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


async def test_scrape():
    """Test scraping posts"""
    print("\n" + "=" * 60)
    print("TEST 2: Scrape Telegram Posts")
    print("=" * 60)

    # Test with Durov's channel
    test_url = "https://t.me/durov"
    print(f"\nScraping from: {test_url}")
    print("Fetching 10 posts...")

    try:
        scraper = TelegramScraper(test_url)
        posts = await scraper.scrape(limit=10)

        print(f"\n✅ Scraped {len(posts)} posts")

        # Display first 3 posts
        print("\nFirst 3 posts:")
        for i, post in enumerate(posts[:3], 1):
            print(f"\n--- Post {i} ---")
            print(f"  ID: {post['platform_post_id']}")
            print(f"  Date: {post['posted_at']}")
            print(f"  Text: {post['text'][:100]}..." if len(post['text']) > 100 else f"  Text: {post['text']}")
            print(f"  Views: {post['reactions']['views']}")
            print(f"  Forwards: {post['reactions']['forwards']}")
            print(f"  Comments: {post['reactions']['comments']}")
            print(f"  Media: {len(post['media'])} items")
            print(f"  Link: {post['link']}")

        return len(posts) > 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_different_url_formats():
    """Test different URL formats"""
    print("\n" + "=" * 60)
    print("TEST 3: Different URL Formats")
    print("=" * 60)

    test_urls = [
        "https://t.me/durov",
        "t.me/durov",
        "@durov",
        "durov"
    ]

    for url in test_urls:
        print(f"\nTesting: {url}")
        try:
            scraper = TelegramScraper(url)
            print(f"  ✅ Parsed handle: {scraper.handle}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def check_credentials():
    """Check if Telegram credentials are configured"""
    print("=" * 60)
    print("CHECKING CREDENTIALS")
    print("=" * 60)

    settings = get_settings()

    print(f"\nTelegram API ID: {'✅ Configured' if settings.telegram_api_id else '❌ Not set'}")
    print(f"Telegram API Hash: {'✅ Configured' if settings.telegram_api_hash else '❌ Not set'}")
    print(f"Session Name: {settings.telegram_session_name}")

    print(f"\nAWS Access Key: {'✅ Configured' if settings.aws_access_key_id else '⚠️  Not set (media will be skipped)'}")
    print(f"AWS S3 Bucket: {settings.aws_s3_bucket}")

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("\n❌ Telegram credentials not configured!")
        print("\nPlease:")
        print("1. Go to https://my.telegram.org/apps")
        print("2. Create an application")
        print("3. Copy api_id and api_hash")
        print("4. Add to .env file:")
        print("   TELEGRAM_API_ID=your_api_id")
        print("   TELEGRAM_API_HASH=your_api_hash")
        return False

    return True


async def main():
    """Run all tests"""
    print("\n🚀 Telegram Scraper Test Suite\n")

    # Check credentials first
    if not await check_credentials():
        print("\n⚠️  Cannot run tests without credentials")
        return

    # Run tests
    results = []

    # Test 1: Verify
    results.append(("Verify", await test_verify()))

    # Test 2: Scrape
    results.append(("Scrape", await test_scrape()))

    # Test 3: URL formats
    await test_different_url_formats()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")

    if total_passed == len(results):
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
