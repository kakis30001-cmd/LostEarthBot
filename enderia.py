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

# Глобальная история диалогов
chat_history = {}

def get_history_key(user_id: int, chat_id: int) -> str:
    return f"{user_id}_{chat_id}"

def add_to_history(user_id: int, chat_id: int, username: str, message: str, response: str = None):
    key = get_history_key(user_id, chat_id)
    if key not in chat_history:
        chat_history[key] = []
    
    chat_history[key].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "username": username,
        "message": message,
        "response": response
    })
    
    # Оставляем последние 30 сообщений для контекста
    if len(chat_history[key]) > 30:
        chat_history[key] = chat_history[key][-30:]

def get_history_context(user_id: int, chat_id: int) -> str:
    key = get_history_key(user_id, chat_id)
    if key not in chat_history or not chat_history[key]:
        return ""
    
    context = "Предыдущий диалог:\n"
    for msg in chat_history[key][-10:]:  # последние 10 сообщений для контекста
        context += f"{msg['username']}: {msg['message']}\n"
        if msg['response']:
            context += f"Эндерия: {msg['response']}\n"
    return context

async def get_enderia_response(user_id: int, chat_id: int, user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с историей диалога"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Получаем историю диалога
    history_context = get_history_context(user_id, chat_id)
    
    # Формируем полную инструкцию с историей
    if history_context:
        full_instruction = f"{ENDERIA_PROMPT}\n\n{history_context}\n\nТекущая дата и время: {current_time}. Игрок {username} написал: {user_message}"
    else:
        full_instruction = f"{ENDERIA_PROMPT}\n\nТекущая дата и время: {current_time}. Игрок {username} написал: {user_message}"
    
    # Отправляем запрос в Gemini
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=user_message,
        config=ai_types.GenerateContentConfig(
            system_instruction=full_instruction,
            temperature=0.9,
        ),
    )
    
    result = response.text if response.text else None
    
    # Сохраняем в историю
    if result:
        add_to_history(user_id, chat_id, username, user_message, result)
    else:
        add_to_history(user_id, chat_id, username, user_message, None)
    
    return result

def should_respond(message_text: str) -> bool:
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
