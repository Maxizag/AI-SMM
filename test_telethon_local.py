from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv('TELEGRAM_API_ID'))
api_hash = os.getenv('TELEGRAM_API_HASH')
session_string = os.getenv('TELEGRAM_STRING_SESSION', '')

print(f"API ID: {api_id}")
print(f"Session string length: {len(session_string)}")

try:
    with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        print("✅ Подключение успешно!")
        me = client.get_me()
        print(f"Залогинен как: {me.first_name} (@{me.username})")
        
        # Попробуем получить канал
        print("\n🔍 Пробую получить канал @durov...")
        entity = client.get_entity('durov')
        print(f"✅ Канал найден: {entity.title}")
        print(f"   Username: @{entity.username}")
        print(f"   Participants: {entity.participants_count if hasattr(entity, 'participants_count') else 'N/A'}")
        
except Exception as e:
    print(f"❌ Ошибка: {type(e).__name__}: {e}")
