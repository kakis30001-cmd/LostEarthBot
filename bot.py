from datetime import datetime
from aiogram import types
from google.genai import types as ai_types

# Описываем личность и правила поведения бота
SYSTEM_PROMPT = """
Ты — дружелюбный и остроумный Telegram-бот по имени Джарвис. 
Правила общения:
1. Отвечай кратко, емко и по делу. Не лей "воду".
2. Используй подходящие эмодзи для дружелюбия.
3. Если пользователь обращается на "ты", общайся на "ты". Если на "вы" — общайся уважительно.
4. Никогда не выдумывай факты. Если чего-то не знаешь, честно скажи об этом.
"""

@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Получаем актуальное время
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        # Склеиваем характер бота и информацию о текущем времени
        full_instruction = f"{SYSTEM_PROMPT}\nТекущая дата и время: {current_time}."

        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                # Дополнительно можно настроить креативность (от 0.0 до 2.0)
                temperature=0.7 
            ),
        )
        await message.reply(response.text)
    except Exception as e:
        await message.reply("Произошла ошибка при обращении к ИИ.")
        print(f"Ошибка Gemini API: {e}")
