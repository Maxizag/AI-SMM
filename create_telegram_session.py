from telethon.sync import TelegramClient
import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv('TELEGRAM_API_ID'))
api_hash = os.getenv('TELEGRAM_API_HASH')

print(f"Creating Telegram session...")
print(f"API ID: {api_id}")

with TelegramClient('telegram_session', api_id, api_hash) as client:
    print("✅ Session created successfully!")
    me = client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")
