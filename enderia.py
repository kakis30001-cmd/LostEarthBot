import os
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

from prompts import ENDERIA_SYSTEM_PROMPT

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

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
    if len(chat_history[key]) > 30:
        chat_history[key] = chat_history[key][-30:]

def get_history_context(user_id: int, chat_id: int) -> str:
    key = get_history_key(user_id, chat_id)
    if key not in chat_history or not chat_history[key]:
        return ""
    context = "Predyduschy dialog:\n"
    for msg in chat_history[key][-10:]:
        context += f"{msg['username']}: {msg['message']}\n"
        if msg['response']:
            context += f"Enderia: {msg['response']}\n"
    return context

async def get_enderia_response(user_id: int, chat_id: int, user_message: str, username: str, online: int = 0) -> str:
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        history_context = get_history_context(user_id, chat_id)
        
        if history_context:
            full_instruction = f"{ENDERIA_SYSTEM_PROMPT}\n\n{history_context}\n\nTime: {current_time}\nOnline: {online} players\n{username}: {user_message}\n\nAnswer as Enderia (short, 2-4 sentences, with premium emojis):"
        else:
            full_instruction = f"{ENDERIA_SYSTEM_PROMPT}\n\nTime: {current_time}\nOnline: {online} players\n{username}: {user_message}\n\nAnswer as Enderia (short, 2-4 sentences, with premium emojis):"
        
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.9,
                max_output_tokens=200,
            ),
        )
        
        result = response.text if response.text else None
        if result:
            add_to_history(user_id, chat_id, username, user_message, result)
        else:
            add_to_history(user_id, chat_id, username, user_message, None)
        
        return result
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["ender", "enderia", "endi", "enдер", "эндер", "эндерия", "энди", "ендер"]
    return any(k in text_lower for k in keywords)
