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

MODELS_CHAIN = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen2.5-7b-instruct",
    "google/gemini-flash-1.5",
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
user_memory = defaultdict(lambda: deque(maxlen=90))  # 90 сообщений
user_greeted = {}  # время последнего приветствия
user_last_message_time = defaultdict(lambda: datetime.now())
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    """добавляет сообщение в память"""
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str) -> str:
    """возвращает последние сообщения диалога для контекста"""
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username])[-90:])  # последние 90 сообщений

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = None

def can_greet(username: str) -> bool:
    """проверяет, можно ли поздороваться (не прошло ли 2 часа)"""
    if username not in user_greeted or user_greeted[username] is None:
        return True
    last_greet = user_greeted[username]
    if isinstance(last_greet, str):
        last_greet = datetime.fromisoformat(last_greet)
    return datetime.now() - last_greet > timedelta(hours=2)

def mark_greeted(username: str):
    """отмечает время приветствия"""
    user_greeted[username] = datetime.now().isoformat()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "ку", "доброе утро", "добрый день", "добрый вечер"]
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
        who = "бот" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_messages_list = [
    "народ, как дела на фермах? у меня криперы уже 3 уровень",
    "что молчим? пойдёмте вместе на сервер",
    "эй, кто хочет сыграть в футбол? пиши 'энди футбол 100'",
    "не забывайте, на мирный режим нужна заявка через бота",
    "айпи сервера: java 150.241.85.40:25565, bedrock 150.241.85.40:19132",
    "официальный тгк сервера @LostEarthSMP, там все новости",
    "кто хочет поиграть в кубик? ставлю 100 xp",
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
    user_last_message_time[username] = datetime.now()
    
    await save_chat_message(username, user_message, is_bot=False)
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    can_say_greeting = can_greet(username)
    
    context = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    # просто позвали по имени
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # приветствие только если прошло 2 часа и это не ответ на сообщение
    if is_greeting_msg and not is_reply:
        if can_say_greeting:
            mark_greeted(username)
            response = f"{E_CAT_DANCE} привет, {username} {E_HEART}"
            add_to_memory(username, user_message, response)
            await save_chat_message(username, response, is_bot=True)
            await save_andy_dialog(username, user_message, response)
            return response
        else:
            response = f"{E_CAT_OK} {username} {E_HEART}"
            add_to_memory(username, user_message, response)
            await save_chat_message(username, response, is_bot=True)
            await save_andy_dialog(username, user_message, response)
            return response
    
    # ии ответ
    if OPENROUTER_API_KEY:
        try:
            system_prompt = f"""ты энди, девушка-эндермен

история диалога с {username}:
{context}

важные правила:
1. не подписывай сообщения как "энди" - это и так понятно
2. не пиши "привет" если уже здоровались недавно
3. отвечай развёрнуто, но по делу
4. если игрок пишет "почему" - посмотри в историю и объясни причину
5. если игрок спрашивает про онлайн - скажи что сейчас {current_online}/{current_max}
6. если спрашивают про сервер - дай айпи и про режимы
7. пиши с маленькой буквы
8. используй эмодзи {E_CAT_DANCE} {E_HEART} {E_MAGIC}
9. не ставь подпись в конце

информация о сервере lostearth (если спросят):
- режимы: мирный (нужна заявка через бота) и smp (без заявки)
- ip java: 150.241.85.40:25565
- ip bedrock: 150.241.85.40:19132
- тг канал: @LostEarthSMP
- админ: @pelmewki379

игры в боте: энди кубик, энди футбол, энди плюнуть, энди фарма

текущее сообщение от {username}: {user_message}

ответь как энди (с маленькой буквы, с эмодзи, без подписи):"""
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": model,
                                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                                "max_tokens": 1000,
                                "temperature": 0.85,
                            },
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                except Exception as e:
                    print(f"модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"ошибка ии: {e}")
    
    # fallback
    fallbacks = [
        f"{E_CAT_DANCE} {username} {E_HEART}",
        f"{E_CAT_OK} слушаю, {username} {E_HEART}",
    ]
    
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
