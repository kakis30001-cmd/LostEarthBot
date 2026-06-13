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
user_last_messages = defaultdict(lambda: deque(maxlen=5))
user_greeted = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Энди: {bot_response}")
    user_last_messages[username].append(user_message)

def get_last_user_messages(username: str) -> list:
    return list(user_last_messages.get(username, []))

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_last_messages:
        user_last_messages[username].clear()
    if username in user_greeted:
        user_greeted[username] = False

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

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_messages = [
    "Народ, как дела? У меня фарма уже 5 уровень! 🐱",
    "Что молчим? Пойдёмте вместе играть! ✨",
    "Эй, кто хочет сыграть в футбол? Ставлю 100 XP! ⚽",
    "Как успехи у всех? Много опыта нафармили? 💜",
    "На сервере сейчас {online} игроков! Заходите! 🎮",
    "Не забывайте собирать фарму! 🏭",
]

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(random.randint(1800, 3600))
        if current_online > 0:
            msg = random.choice(spontaneous_messages)
            msg = msg.replace("{online}", str(current_online))
            await bot.send_message(chat_id, f"{E_CAT_DANCE} {msg} {E_HEART}", parse_mode="HTML")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    
    last_messages = get_last_user_messages(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} Слушаю, {username}! Что хотел узнать? {E_HEART}"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        return response
    
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{E_CAT_DANCE} {username}, мы уже общаемся! {E_JOYSTICK}"
        add_to_memory(username, user_message, response)
        return response
    
    if OPENROUTER_API_KEY:
        try:
            last_msgs = "\n".join([f"- {msg}" for msg in last_messages[-5:]]) if last_messages else "пока пусто"
            
            system_prompt = f"""Ты — Энди, девушка-эндермен.

ПОСЛЕДНИЕ СООБЩЕНИЯ {username}:
{last_msgs}

НЕ ЗДОРОВАЙСЯ, если уже общались!

ИНФОРМАЦИЯ:
- Сервер: LostEarth, IP: 150.241.85.40:25565
- Админ: @pelmewki379
- Онлайн: {current_online}/{current_max}

ИГРЫ: энди кубик 100, энди футбол 100, энди плюнуть, энди фарма

ПРАВИЛА: отвечай коротко (2-4 предложения), используй эмодзи 🐱💜✨

Ответь игроку {username}: {user_message}"""
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": model,
                                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
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
                except:
                    continue
        except:
            pass
    
    fallbacks = [
        f"{E_CAT_DANCE} {username}, я тут! Хочешь сыграть? Напиши 'энди кубик 100' {E_HEART}",
        f"{E_MAGIC} {username}, телепортнулась к тебе! {E_JOYSTICK}",
        f"{E_CROWN} {username}, на сервере {current_online}/{current_max} игроков! {E_RABBIT}"
    ]
    
    response = random.choice(fallbacks)
    if not already_greeted and not is_reply:
        mark_greeted(username)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response
