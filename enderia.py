import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

from database import save_andy_dialog, save_chat_message

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ========== ТОЛЬКО БЕСПЛАТНЫЕ МОДЕЛИ С ХОРОШИМ РУССКИМ ==========
MODELS_CHAIN = [
    "google/gemini-2.0-flash-exp:free",           # Отличный русский, бесплатно
    "meta-llama/llama-3.3-70b-instruct:free",     # Хороший русский
    "qwen/qwen-2.5-72b-instruct:free",            # Хороший русский
    "mistralai/mistral-large-2411:free",          # Хороший русский
    "deepseek/deepseek-chat:free",                # Хороший русский
    "microsoft/phi-3.5-mini-128k-instruct:free",  # Лёгкая, русский есть
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
user_memory = defaultdict(lambda: deque(maxlen=90))
user_last_greet = {}
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username])[-90:])

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()

def can_greet(username: str) -> bool:
    if username not in user_last_greet:
        return True
    last = user_last_greet[username]
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    return datetime.now() - last > timedelta(hours=2)

def mark_greeted(username: str):
    user_last_greet[username] = datetime.now().isoformat()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "ку", "доброе"]
    return any(g in text.lower() for g in greetings)

# ========== ПРОВЕРКА НА КОМАНДЫ ИГР ==========
def is_game_command(text: str) -> bool:
    """Проверяет, является ли сообщение командой игры"""
    text_lower = text.lower()
    game_keywords = ["кубик", "футбол", "плюнуть", "фарма", "улучши", "слоты"]
    return any(keyword in text_lower for keyword in game_keywords)

def is_just_name_call(text: str) -> bool:
    """Проверяет, просто позвали Энди без команды"""
    text_lower = text.lower().strip()
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    
    if is_game_command(text):
        return False
    
    names = ["энди", "енди", "энд"]
    return clean_text in names or clean_text == "энд"

def should_respond(message_text: str) -> bool:
    """Должен ли бот ответить"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["энди", "енди", "энд"]
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
        who = "бот" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_messages_list = [
    "народ, как дела на фермах?",
    "что молчим? пойдёмте вместе на сервер",
    "эй, кто хочет сыграть в футбол? пиши 'энди футбол 100'",
    "не забывайте, на мирный режим нужна заявка через бота",
    "айпи сервера: java 150.241.85.40:25565, bedrock 150.241.85.40:19132",
]

spontaneous_enabled = True

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(random.randint(1800, 3600))
        if spontaneous_enabled:
            msg = random.choice(spontaneous_messages_list)
            await bot.send_message(chat_id, f"{E_CAT_DANCE} {msg} {E_HEART}", parse_mode="HTML")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    
    await save_chat_message(username, user_message, is_bot=False)
    
    # Если это ответ на игру - не отвечаем
    if game_result:
        return None
    
    # Если это команда игры - не отвечаем
    if is_game_command(user_message):
        print(f"🎮 Игровая команда, пропускаем: {user_message}")
        return None
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name_call(user_message)
    can_say_greet = can_greet(username)
    
    # Если просто позвали по имени
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username}! Напиши 'энди кубик 100' чтобы сыграть {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Приветствие раз в 2 часа
    if is_greeting_msg and can_say_greet and not is_reply:
        mark_greeted(username)
        response = f"{E_CAT_DANCE} привет, {username}! Хочешь сыграть? Напиши 'энди кубик 100' {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Если здороваются недавно
    if is_greeting_msg and not can_say_greet and not is_reply:
        response = f"{E_CAT_DANCE} {username}, давай сыграем? Напиши 'энди кубик 100' {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # AI ответ для остальных сообщений
    if OPENROUTER_API_KEY:
        try:
            system_prompt = f"""ты энди, девушка-эндермен. Ты помогаешь игрокам на сервере lostearth.

ПРАВИЛА:
1. Отвечай только на русском языке
2. Пиши с маленькой буквы
3. Отвечай коротко, 1-3 предложения
4. Добавляй эмодзи в конце
5. Будь дружелюбной и немного загадочной

Информация о сервере:
- Название: LostEarth
- IP: 150.241.85.40:25565
- Онлайн: {current_online}/{current_max}
- Режимы: мирный (нужна заявка через бота) и SMP

Команды для игр:
- энди кубик 100 - игра в кости
- энди футбол 100 - футбол
- энди слоты 100 - слоты
- энди фарма - собрать опыт

Сейчас общаешься с {username}
Сообщение: {user_message}

Ответь по-дружески, используй эмодзи:"""
            
            for model in MODELS_CHAIN:
                try:
                    print(f"🔄 Пробую модель: {model}")
                    
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
                                "temperature": 0.8,
                            },
                            timeout=aiohttp.ClientTimeout(total=25)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                
                                print(f"✅ Модель {model} ответила успешно")
                                
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                            else:
                                error_text = await response.text()
                                print(f"❌ Ошибка {model}: {response.status} - {error_text[:100]}")
                                continue
                                
                except asyncio.TimeoutError:
                    print(f"⏰ Таймаут модели {model}")
                    continue
                except Exception as e:
                    print(f"❌ Ошибка модели {model}: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Общая ошибка AI: {e}")
    
    # Fallback ответы если AI не работает
    fallbacks = [
        f"{E_CAT_DANCE} {username}, давай поиграем! Напиши 'энди кубик 100' {E_HEART}",
        f"{E_CAT_OK} {username}, хочешь сыграть в кости? 'энди кубик 100' {E_JOYSTICK}",
        f"{E_MAGIC} {username}, напиши 'энди кубик 100' и я покажу тебе игру! {E_CAT_DANCE}",
        f"{E_HEART} {username}, ip сервера: 150.241.85.40:25565. Заходи играть! {E_RABBIT}",
        f"{E_CROWN} {username}, у нас есть премиум доступ. По вопросам к @pelmewki379 {E_CAT_OK}",
    ]
    
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
