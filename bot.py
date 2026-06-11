import asyncio
import os
from datetime import datetime
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from flask import Flask
from google import genai
from google.genai import types as ai_types  # Правильный импорт для версии 1.0.0

# Загружаем переменные
load_dotenv()

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Flask для Railway
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot is alive!", 200


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# Инициализация ИИ и Telegram
ai_client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Системный промпт
SYSTEM_PROMPT = """
Ты — дружелюбный и остроумный Telegram-бот по имени Джарвис. 
Правила общения:
1. Отвечай кратко, емко и по делу.
2. Используй подходящие эмодзи для дружелюбия.
3. Если пользователь обращается на "ты", общайся на "ты". Если на "вы" — общайся уважительно.
4. Никогда не выдумывай факты.
"""


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Привет! Напиши мне, и я отвечу с помощью Gemini.")


@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Получаем актуальное время
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        full_instruction = (
            f"{SYSTEM_PROMPT}\nТекущая дата и время сервера: {current_time}."
        )

        # Запрос к Gemini
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.7,
            ),
        )
        await message.reply(response.text)
    except Exception as e:
        await message.reply("Произошла ошибка при обращении к ИИ.")
        print(f"Ошибка Gemini API: {e}")


async def main():
    # Запуск Flask в потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Бот успешно запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
