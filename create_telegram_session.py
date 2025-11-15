#!/usr/bin/env python3
"""
Script to create Telegram session file for Telethon

This script must be run LOCALLY (not in Docker) to interactively
authenticate with Telegram and create a session file.

Usage:
    1. Make sure you have TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
    2. Run: python create_telegram_session.py
    3. Enter your phone number when prompted
    4. Enter the code sent to your Telegram app
    5. Session file will be created in the project root
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

# Load environment variables
env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    print("❌ Error: .env file not found!")
    print(f"   Please create .env file in {Path(__file__).parent}")
    sys.exit(1)

load_dotenv(env_path)

# Get credentials from .env
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_NAME = os.getenv('TELEGRAM_SESSION_NAME', 'aismm_scraper')

if not API_ID or not API_HASH:
    print("❌ Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
    print("\n📝 To get these credentials:")
    print("   1. Go to https://my.telegram.org/apps")
    print("   2. Log in with your phone number")
    print("   3. Create a new application")
    print("   4. Copy api_id and api_hash to .env file")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    print(f"❌ Error: TELEGRAM_API_ID must be a number, got: {API_ID}")
    sys.exit(1)


async def create_session():
    """Create Telegram session interactively"""

    print("\n🔐 Creating Telegram session...")
    print(f"   Session name: {SESSION_NAME}")
    print(f"   API ID: {API_ID}")
    print(f"   API Hash: {API_HASH[:8]}...")

    # Create client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print("\n📱 Connecting to Telegram...")

    try:
        # Start client (will prompt for phone and code)
        await client.start()

        # Get current user info to verify
        me = await client.get_me()

        print("\n✅ Session created successfully!")
        print(f"   Logged in as: {me.first_name} (@{me.username})")
        print(f"   Phone: {me.phone}")
        print(f"   Session file: {SESSION_NAME}.session")

        print("\n📦 Next steps:")
        print("   1. The session file has been created in the project root")
        print("   2. This file will be automatically mounted to Docker containers")
        print("   3. You can now use the Telegram scraper without authentication prompts")

        await client.disconnect()

        return True

    except Exception as e:
        print(f"\n❌ Error creating session: {e}")
        return False


async def test_session():
    """Test existing session"""

    session_file = f"{SESSION_NAME}.session"

    if not Path(session_file).exists():
        print(f"❌ Session file not found: {session_file}")
        return False

    print(f"\n🧪 Testing session: {session_file}")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Session is not authorized")
            return False

        me = await client.get_me()
        print(f"✅ Session is valid!")
        print(f"   Logged in as: {me.first_name} (@{me.username})")

        await client.disconnect()
        return True

    except Exception as e:
        print(f"❌ Error testing session: {e}")
        return False


async def main():
    """Main function"""

    session_file = f"{SESSION_NAME}.session"

    # Check if session already exists
    if Path(session_file).exists():
        print(f"⚠️  Session file already exists: {session_file}")
        print("\nOptions:")
        print("  1. Test existing session")
        print("  2. Create new session (will overwrite)")
        print("  3. Exit")

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            await test_session()
        elif choice == "2":
            print("\n⚠️  This will overwrite the existing session!")
            confirm = input("Are you sure? (yes/no): ").strip().lower()
            if confirm == "yes":
                await create_session()
            else:
                print("Cancelled.")
        else:
            print("Exiting...")
    else:
        # No session exists, create new one
        await create_session()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(0)
