"""
Telegram hesabina ilk giris - session dosyasi olusturur.
Sadece bir kez calistir.
"""
import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION  = "telegram_session"

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"\nGiris basarili: {me.first_name} (@{me.username})")
    print(f"Session dosyasi olusturuldu: {SESSION}.session")
    await client.disconnect()

asyncio.run(main())
