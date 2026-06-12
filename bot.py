import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer("✅ Бот работает! Напиши что-нибудь")

@dp.message()
async def handle_all(message: Message):
    # Отвечаем на КАЖДОЕ сообщение
    await message.answer(f"✅ Я получила: {message.text}")

async def main():
    print("🚀 БОТ ЗАПУЩЕН (тестовый режим)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
