from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv('TELEGRAM_API_ID'))
api_hash = os.getenv('TELEGRAM_API_HASH')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("✅ Авторизация успешна!")
    print("\nДобавь эту строку в .env:")
    print(f"TELEGRAM_STRING_SESSION={client.session.save()}")
