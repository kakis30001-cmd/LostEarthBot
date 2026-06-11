import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from google import genai
from google.genai import types

# Настройки
logging.basicConfig(level=logging.INFO)
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Функция ответа Эндерии
def get_ai_response(text, username):
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"Ты Эндерия. Игрок {username} написал: {text}. Ответь коротко и мило, с эмодзи 💜"
        )
        return response.text
    except Exception as e:
        return f"Ошибка: {str(e)}"

@dp.message()
async def handle_message(message: Message):
    if any(word in message.text.lower() for word in ["эндер", "эндерия", "энди"]):
        answer = get_ai_response(message.text, message.from_user.first_name)
        await message.reply(answer)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
