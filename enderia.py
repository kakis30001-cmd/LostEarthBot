import os
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Промпт Эндерии
ENDERIA_PROMPT = (
    "Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth. "
    "Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации. "
    "Обожаешь котиков, аниме и зайчиков. Отвечай коротко, 2-4 предложения. "
    "Используй эмодзи 🐱 💃 🐰 💜. Обращайся к игроку по имени. "
    "Информация о сервере: IP Java 150.241.85.40:25565, IP Bedrock 150.241.85.40:19132, версия 1.21-1.26+. "
    "Мирный режим: PvP только по согласию, доступ по заявкам. Админ: @pelmewki379. "
    "Донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽."
)

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Формируем полную инструкцию
    full_instruction = f"{ENDERIA_PROMPT} Текущая дата и время: {current_time}. Игрок {username} написал: {user_message}"
    
    # Используем gemini-2.5-flash-lite (больше запросов)
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=user_message,
        config=ai_types.GenerateContentConfig(
            system_instruction=full_instruction,
            temperature=0.9,
        ),
    )
    
    return response.text if response.text else None

def should_respond(message_text: str) -> bool:
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
