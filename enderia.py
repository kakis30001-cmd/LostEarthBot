import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

from database import save_andy_dialog, get_andy_dialogs, save_chat_message

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 5 моделей ИИ как было
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
user_memory = defaultdict(lambda: deque(maxlen=50))
user_greeted = {}
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"andy: {bot_response}")

def get_user_context(username: str) -> str:
    """возвращает последние сообщения диалога для контекста"""
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    # берём последние 20 сообщений
    context = "\n".join(list(user_memory[username])[-20:])
    return context

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = False

def has_already_greeted(username: str) -> bool:
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    user_greeted[username] = True

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
        who = "энди" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_messages = [
    "народ, как дела на фермах? у меня криперы уже 3 уровень! {cat}",
    "что молчим? пойдёмте вместе на сервер, там сейчас {online} игроков! {magic}",
    "эй, кто хочет сыграть в футбол? пиши 'энди футбол 100'! {joystick}",
]

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(random.randint(1800, 3600))
        msg = random.choice(spontaneous_messages)
        msg = msg.replace("{online}", str(current_online))
        msg = msg.replace("{cat}", E_CAT_DANCE)
        msg = msg.replace("{magic}", E_MAGIC)
        msg = msg.replace("{joystick}", E_JOYSTICK)
        await bot.send_message(chat_id, f"{E_CAT_DANCE} {msg}", parse_mode="HTML")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    
    await save_chat_message(username, user_message, is_bot=False)
    
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # получаем полный контекст диалога
    context = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    # если позвали по имени
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username}! что хотел узнать? {E_HEART}"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # если уже здоровались и написали привет - не здороваемся заново
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{E_CAT_DANCE} да, {username}, я тут! что случилось? {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # пытаемся получить ответ от ии с полным контекстом
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            # важный промпт с контекстом
            system_prompt = f"""ты энди, девушка-эндермен. ты должна внимательно читать историю диалога и отвечать последовательно!

вот история диалога с {username}:
{context}

правила которые ты должна строго соблюдать:
1. НЕ ПИШИ ПРО СЕРВЕР В КАЖДОМ СООБЩЕНИИ! только если игрок сам спросил про сервер
2. отвечай по существу вопроса, не повторяй одно и то же
3. если игрок пишет "почему" - посмотри в историю, на что он отвечает
4. если игрок пишет "понял" или "ок" - просто ответь "хорошо" или "отлично"
5. пиши с маленькой буквы
6. используй эмодзи {E_CAT_DANCE} {E_HEART} {E_MAGIC}
7. отвечай коротко (1-3 предложения)

информация о сервере (говори только если спросят):
- режимы: мирный (нужна заявка) и smp (без заявки)
- ip java: 150.241.85.40:25565, bedrock: 150.241.85.40:19132
- тг канал: @LostEarthSMP
- онлайн сейчас: {current_online}/{current_max}

игры в боте:
- энди кубик [ставка] - кости
- энди футбол [ставка] - футбол
- энди плюнуть - плюнуть в игрока

текущее сообщение от {username}: "{user_message}"

ответь как энди (с маленькой буквы, с эмодзи, НЕ ПИШИ ПРО СЕРВЕР если не спрашивали):"""
            
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
                                "max_tokens": 350,
                                "temperature": 0.85,
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
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                except Exception as e:
                    print(f"модель {model} ошибка: {e}")
                    continue
        except Exception as e:
            print(f"ошибка ии: {e}")
    
    # fallback если ии не ответил
    fallbacks = [
        f"{E_CAT_DANCE} {username}, я тут! {E_HEART}",
        f"{E_MAGIC} {username}, слушаю! {E_CAT_OK}",
        f"{E_HEART} да, {username}?",
    ]
    
    response = random.choice(fallbacks)
    if not already_greeted and not is_reply:
        mark_greeted(username)
    
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
