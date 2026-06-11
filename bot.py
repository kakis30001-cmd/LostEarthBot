import asyncio
import os
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from flask import Flask
from google import genai

# Загружаем переменные (для локальных тестов)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Flask для Railway (Health Check)
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot is alive!", 200


def run_flask():
    # Railway автоматически передает порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# Инициализация ИИ и Telegram
ai_client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Привет! Напиши мне, и я отвечу с помощью Gemini.")


@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Синтаксис генерации для google-genai==1.0.0
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
        )
        await message.reply(response.text)
    except Exception as e:
        await message.reply("Произошла ошибка при обращении к ИИ.")
        print(f"Ошибка Gemini API: {e}")


async def main():
    # Запускаем Flask в отдельном потоке, чтобы Railway видел живой порт
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Бот успешно запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
