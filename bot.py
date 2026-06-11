import asyncio
import os
from datetime import datetime
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from flask import Flask
from google import genai
from google.genai import types as ai_types

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")  # Ваша переменная на Railway
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Flask для проверки портов (Health Check) Railway
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot is alive!", 200


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# Инициализация клиентов
ai_client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Системный промпт (инструкция для роли Джарвиса)
SYSTEM_PROMPT = (
    "Ты — дружелюбный и остроумный Telegram-бот по имени Джарвис. "
    "Отвечай кратко, емко и по делу. Используй подходящие эмодзи для дружелюбия. "
    "Если пользователь обращается на 'ты', общайся на 'ты'. Если на 'вы' — общайся уважительно. "
    "Никогда не выдумывай факты."
)


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! Я Джарвис. Напиши мне, и я отвечу с помощью Gemini."
    )


@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    # Показываем статус "печатает..." в Telegram
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Формируем актуальное время для системного промпта
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        full_instruction = (
            f"{SYSTEM_PROMPT} Текущая дата и время сервера: {current_time}."
        )

        # Отправляем запрос в Gemini API версии 1.0.0
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.7,
            ),
        )

        # Отправляем ответ пользователю, если он сгенерирован
        if response.text:
            await message.reply(response.text)
        else:
            await message.reply(
                "Gemini вернул пустой ответ (возможно, сработали фильтры безопасности)."
            )

    except Exception as e:
        # Выводим ошибку прямо в чат для быстрой диагностики
        await message.reply(f"Ошибка ИИ: {str(e)[:150]}")
        print(f"Полная ошибка в логах: {e}")


async def main():
    # Запускаем веб-сервер Flask в фоновом режиме для Railway
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Бот Джарвис успешно запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
