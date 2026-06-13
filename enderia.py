import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "meta-llama/llama-3.3-70b-instruct",
]

# ========== ПРЕМИУМ ЭМОДЗИ ==========
ENDERIA_EMOJI = {
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "cat_up": "5269698007724499331",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "heart": "5199427253225667842",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "magic": "5474144592817318927",
    "joystick": "5870717606364713020",
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CAT_DANCE = emoji(ENDERIA_EMOJI["cat_dance"], "🐱")
E_CAT_OK = emoji(ENDERIA_EMOJI["cat_ok"], "👍")
E_CAT_UP = emoji(ENDERIA_EMOJI["cat_up"], "👍")
E_CAT_SURPRISED = emoji(ENDERIA_EMOJI["cat_surprised"], "😲")
E_RABBIT = emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")
E_ANIME = emoji(ENDERIA_EMOJI["anime_dance"], "💃")
E_HEART = emoji(ENDERIA_EMOJI["heart"], "💜")
E_CROWN = emoji(ENDERIA_EMOJI["crown"], "👑")
E_HOUSE = emoji(ENDERIA_EMOJI["house"], "🏠")
E_NOTE = emoji(ENDERIA_EMOJI["note"], "📝")
E_MAGIC = emoji(ENDERIA_EMOJI["magic"], "✨")
E_JOYSTICK = emoji(ENDERIA_EMOJI["joystick"], "🎮")

# ========== ПАМЯТЬ ==========
user_memory = defaultdict(lambda: deque(maxlen=20))
user_last_message_time = {}  # Время последнего сообщения от пользователя
user_conversation_active = {}  # Активен ли диалог

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def is_conversation_active(username: str) -> bool:
    """Проверяет, активен ли диалог (последнее сообщение было меньше 5 минут назад)"""
    if username not in user_last_message_time:
        return False
    time_diff = (datetime.now() - user_last_message_time[username]).total_seconds()
    return time_diff < 300  # 5 минут

def update_last_message_time(username: str):
    user_last_message_time[username] = datetime.now()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "доброе утро", "добрый день", "добрый вечер"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "эндер", "эндерия", "ендер", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "енди"]
    return any(keyword in text_lower for keyword in keywords)

# ========== ОНЛАЙН ==========
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== ОСНОВНАЯ ФУНКЦИЯ С ИИ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "") -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    update_last_message_time(username)
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    conversation_active = is_conversation_active(username)
    
    # Если диалог активен и это не приветствие и не обращение по имени - просто отвечаем
    if conversation_active and not is_greeting_msg and not is_name_call:
        # Продолжаем диалог без приветствия
        pass
    # Если позвали по имени
    elif is_name_call:
        response = f"{E_CAT_OK} Слушаю, {username}! Что хотел узнать? {E_HEART}"
        add_to_memory(username, user_message, response)
        return response
    # Если написали привет и диалог неактивен
    elif is_greeting_msg and not conversation_active:
        response = f"{E_CAT_DANCE} Привет, {username}! Рада тебя видеть! {E_HEART}"
        add_to_memory(username, user_message, response)
        return response
    # Если написали привет но диалог активен - НЕ ЗДОРОВАЕМСЯ!
    elif is_greeting_msg and conversation_active:
        response = f"{E_CAT_OK} {username}, я тут! Что случилось? {E_HEART}"
        add_to_memory(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            # Берём последние 5 сообщений для контекста
            history = ""
            if username in user_memory and len(user_memory[username]) > 0:
                history = "\n".join(list(user_memory[username])[-6:])
            
            system_prompt = f"""Ты — Эндерия (Энди), девушка-эндермен, хранительница Края.

Твой характер: добрая, загадочная, слегка вредная. Говоришь ласково, используешь эмодзи.

ИНФОРМАЦИЯ О СЕРВЕРЕ LOSTEARTH:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Админ: @pelmewki379
- Сейчас онлайн: {current_online}/{current_max} игроков

ВАЖНО: Ты уже общаешься с {username}. НЕ ЗДОРОВАЙСЯ заново! Просто продолжай разговор.

История диалога:
{history if history else "Диалог только начинается"}

Сейчас {username} написал: {user_message}

Ответь коротко (2-4 предложения), по делу, используй эмодзи. НЕ ЗДОРОВАЙСЯ!"""
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_message}
                                ],
                                "max_tokens": 250,
                                "temperature": 0.9,
                            },
                            timeout=aiohttp.ClientTimeout(total=25)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                return result
                except Exception as e:
                    print(f"Модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"Ошибка ИИ: {e}")
    
    # Fallback ответы (без приветствий)
    fallbacks = [
        f"{E_CAT_DANCE} Поняла, {username}! {E_HEART}",
        f"{E_MAGIC} Хорошо, {username}! {E_CAT_OK}",
        f"{E_HEART} Ясно, {username}! {E_RABBIT}",
        f"{E_CROWN} Запомнила, {username}! {E_JOYSTICK}"
    ]
    
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response
