from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv('TELEGRAM_API_ID'))
api_hash = os.getenv('TELEGRAM_API_HASH')
session_string = os.getenv('TELEGRAM_STRING_SESSION', '')

print(f"Session length: {len(session_string)}")

async def test():
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        await client.connect()
        print("✅ Connected!")
        
        # Проверим что авторизованы
        if not await client.is_user_authorized():
            print("❌ Not authorized!")
            return
        
        print("✅ Authorized!")
        entity = await client.get_entity('durov')
        print(f"✅ Got channel: {entity.title}")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
    finally:
        await client.disconnect()

asyncio.run(test())
