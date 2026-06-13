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
user_greeted = {}
last_message_from_bot = {}  # храним последнее сообщение бота для каждого пользователя

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Энди: {bot_response}")

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = False

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def has_already_greeted(username: str) -> bool:
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    user_greeted[username] = True

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["энди", "енди"]
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
        who = "Энди" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== ОСНОВНАЯ ФУНКЦИЯ С ИИ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "") -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # Если это ответ на сообщение Энди - продолжаем диалог без приветствия
    if is_reply:
        # Это ответ на сообщение бота, продолжаем разговор
        pass
    
    # Если позвали по имени
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} Слушаю, {username}! Что хотел узнать? {E_HEART}"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        return response
    
    # Если уже здоровались и это не ответ на сообщение бота - не здороваемся
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{E_CAT_DANCE} {username}, мы уже общаемся! Что случилось? {E_HEART}"
        add_to_memory(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            system_prompt = f"""Ты — Энди, девушка-эндермен, хранительница Края.

Твой характер: добрая, загадочная, слегка вредная. Говоришь ласково, используешь эмодзи.

ИНФОРМАЦИЯ О СЕРВЕРЕ LOSTEARTH:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Админ: @pelmewki379
- Сейчас онлайн: {current_online}/{current_max} игроков

ИГРЫ В ТЕЛЕГРАМ БОТЕ:
- /bet [сумма] - игра в кости (выигрыш x2)
- /football [сумма] - футбол (гол = x2)

ФЕРМЫ ОПЫТА:
- /farms - посмотреть фермы
- /buy_farm - купить ферму
- /upgrade_farm - улучшить ферму
- /claim - собрать опыт

ПРАВИЛА:
1. Если это ответ на твоё сообщение - ПРОДОЛЖАЙ диалог, НЕ ЗДОРОВАЙСЯ
2. Отвечай коротко (2-4 предложения)
3. Будь милой, используй эмодзи 🐱 💜 ✨

Ответь на сообщение игрока {username}: {user_message}"""
            
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
                                
                                if not already_greeted and not is_reply:
                                    mark_greeted(username)
                                
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                return result
                except Exception as e:
                    print(f"Модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"Ошибка ИИ: {e}")
    
    # Fallback
    fallbacks = [
        f"{E_CAT_DANCE} {username}, я тут! Чем могу помочь? {E_HEART}",
        f"{E_MAGIC} {username}, телепортнулась к тебе! {E_CAT_OK}",
        f"{E_HEART} {username}, как дела на сервере? {E_RABBIT}",
        f"{E_CROWN} {username}, на сервере сейчас {current_online}/{current_max} игроков! {E_JOYSTICK}"
    ]
    
    response = random.choice(fallbacks)
    if not already_greeted and not is_reply:
        mark_greeted(username)
    
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response
