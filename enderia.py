import os
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

from prompts import ENDERIA_SYSTEM_PROMPT

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# История диалогов (чтобы Энди помнила о чём говорили)
chat_history = {}

def get_history_key(user_id: int, chat_id: int) -> str:
    """Уникальный ключ для каждого чата"""
    return f"{user_id}_{chat_id}"

def add_to_history(user_id: int, chat_id: int, username: str, message: str, response: str = None):
    """Сохраняет сообщение и ответ в историю"""
    key = get_history_key(user_id, chat_id)
    if key not in chat_history:
        chat_history[key] = []
    
    chat_history[key].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "username": username,
        "message": message,
        "response": response
    })
    
    # Оставляем последние 30 сообщений
    if len(chat_history[key]) > 30:
        chat_history[key] = chat_history[key][-30:]

def get_history_context(user_id: int, chat_id: int) -> str:
    """Возвращает последние сообщения из истории для контекста"""
    key = get_history_key(user_id, chat_id)
    if key not in chat_history or not chat_history[key]:
        return ""
    
    context = "📜 Предыдущий диалог:\n"
    for msg in chat_history[key][-10:]:  # последние 10 сообщений
        context += f"{msg['username']}: {msg['message']}\n"
        if msg['response']:
            context += f"Эндерия: {msg['response']}\n"
    return context

async def get_enderia_response(user_id: int, chat_id: int, user_message: str, username: str, online: int = 0) -> str:
    """Получить ответ от Эндерии с историей диалога"""
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        # Получаем историю диалога для этого чата
        history_context = get_history_context(user_id, chat_id)
        
        # Формируем полную инструкцию с историей и онлайном
        if history_context:
            full_instruction = f"{ENDERIA_SYSTEM_PROMPT}\n\n{history_context}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📅 Текущая дата и время: {current_time}\n📊 Сейчас на сервере онлайн: {online} игроков\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👤 Игрок {username} написал: \"{user_message}\"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nОтветь как Эндерия (мило, с ПРЕМИУМ ЭМОДЗИ, коротко 2-4 предложения):"
        else:
            full_instruction = f"{ENDERIA_SYSTEM_PROMPT}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📅 Текущая дата и время: {current_time}\n📊 Сейчас на сервере онлайн: {online} игроков\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👤 Игрок {username} написал: \"{user_message}\"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nОтветь как Эндерия (мило, с ПРЕМИУМ ЭМОДЗИ, коротко 2-4 предложения):"
        
        # Отправляем запрос в Gemini
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.9,
                max_output_tokens=250,
            ),
        )
        
        result = response.text if response.text else None
        
        # Сохраняем в историю
        if result:
            add_to_history(user_id, chat_id, username, user_message, result)
        else:
            add_to_history(user_id, chat_id, username, user_message, None)
        
        return result
        
    except Exception as e:
        print(f"❌ Gemini ошибка: {e}")
        return None

def should_respond(message_text: str) -> bool:
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд", "ендеря"]
    return any(keyword in text_lower for keyword in keywords)
