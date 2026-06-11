import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from google import genai

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализируем клиентов
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)


# Приветственное сообщение
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! Напиши мне любой вопрос, и я отвечу с помощью Gemini."
    )


# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: types.Message):
    # Отправляем статус "печать...", чтобы пользователь видел активность
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Запрос к актуальной модели Gemini
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
        )
        # Отправляем ответ пользователю
        await message.reply(response.text)
    except Exception as e:
        await message.reply(
            "Произошла ошибка при обращении к ИИ. Попробуйте позже."
        )
        print(f"Ошибка: {e}")


async def main():
    print("Бот успешно запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
