import os
import random
import asyncio
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from google.genai.errors import ClientError
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

# Запасные фразы при ошибках
FALLBACK_RESPONSES = [
    "Ой~ {username}, меня немного зателепортировало! Повтори вопрос через минуту 💜",
    "{username}, энергия Края восстанавливается... Скажи ещё разок! 🐱",
    "*телепортируется обратно* {username}, давай попробуем снова! 💜",
    "{username}, слишком много сообщений! Давай помедленнее 🐰"
]

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с обработкой ошибок"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    full_instruction = f"{ENDERIA_PROMPT} Текущая дата и время: {current_time}. Игрок {username} написал: {user_message}"
    
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.9,
            ),
        )
        
        if response and response.text:
            return response.text
        else:
            return f"{random.choice(FALLBACK_RESPONSES).format(username=username)}"
            
    except ClientError as e:
        # Ошибки Google API
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print(f"[WARN] Лимит Gemini: {e}")
            return f"⚠️ {username}, я получила слишком много вопросов! Подожди 30 секунд и напиши снова 💜"
        else:
            print(f"[ERROR] ClientError: {e}")
            return f"🤖 {username}, у меня технические трудности. Попробуй позже!"
            
    except Exception as e:
        # Любые другие ошибки
        print(f"[ERROR] Неизвестная ошибка: {e}")
        return f"❌ {username}, что-то пошло не так... Давай попробуем ещё раз!"

def should_respond(message_text: str) -> bool:
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
