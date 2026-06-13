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
user_memory = defaultdict(lambda: deque(maxlen=30))  # увеличил память до 30 сообщений
user_greeted = {}
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"энди: {bot_response}")

def get_user_context(username: str) -> str:
    """Возвращает последние сообщения диалога"""
    if username not in user_memory or len(user_memory[username]) == 0:
        return "диалог только начинается"
    return "\n".join(list(user_memory[username])[-20:])  # последние 20 сообщений

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "доброе утро", "добрый день", "добрый вечер"]
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
current_server_status = "онлайн"

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players
    if online == 0:
        global current_server_status
        current_server_status = "пустует"

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
    "не забывайте, на мирный режим нужна заявка через бота! а на smp можно сразу заходить {house}",
    "айпи сервера: java 150.241.85.40:25565, bedrock 150.241.85.40:19132 {rabbit}",
    "официальный тгк сервера @LostEarthSMP, там все новости! {heart}",
]

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(random.randint(1800, 3600))
        if current_online > 0 or True:  # отправляем даже если 0 онлайн
            msg = random.choice(spontaneous_messages)
            msg = msg.replace("{online}", str(current_online))
            msg = msg.replace("{cat}", E_CAT_DANCE)
            msg = msg.replace("{magic}", E_MAGIC)
            msg = msg.replace("{joystick}", E_JOYSTICK)
            msg = msg.replace("{house}", E_HOUSE)
            msg = msg.replace("{rabbit}", E_RABBIT)
            msg = msg.replace("{heart}", E_HEART)
            await bot.send_message(chat_id, f"{E_CAT_DANCE} {msg}", parse_mode="HTML")

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max, current_server_status
    
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    
    # Сохраняем сообщение в БД
    await save_chat_message(username, user_message, is_bot=False)
    
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # Получаем историю диалога
    history = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    # Если позвали по имени
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username}! что хотел узнать? {E_HEART}"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Если уже здоровались - не здороваемся
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{E_CAT_DANCE} {username}, мы уже общаемся! {E_JOYSTICK}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            system_prompt = f"""ты энди, девушка-эндермен. ты должна запоминать контекст разговора!

история последних сообщений с {username}:
{history}

важно: используй эту историю чтобы отвечать последовательно! если игрок спрашивает "о чём мы говорили" - посмотри в историю и ответь!

информация о сервере lostearth:
- режимы: мирный (нужна заявка через бота, нет гриферства) и smp (можно рейдить, заявка не нужна)
- ip java: 150.241.85.40:25565
- ip bedrock: 150.241.85.40:19132
- тг канал: @LostEarthSMP
- админ: @pelmewki379
- онлайн сейчас: {current_online}/{current_max}
- статус: {current_server_status}

игры в боте:
- энди кубик [ставка] - игра в кости
- энди футбол [ставка] - футбол
- энди плюнуть - плюнуть в игрока
- энди фарма - собрать опыт

правила:
1. пиши с маленькой буквы, даже в начале предложения!
2. используй премиум эмодзи {E_CAT_DANCE} {E_HEART} {E_MAGIC}
3. если игрок спрашивает "о чём мы говорили" - посмотри в историю и ответь конкретно
4. не выдумывай то, чего не было в истории
5. если не помнишь - скажи честно "не помню точно, напомни"
6. отвечай на русском, коротко (2-4 предложения)
7. всегда зови на сервер

текущее сообщение от {username}: {user_message}

ответь как энди (с маленькой буквы, с эмодзи):"""
            
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
                    print(f"модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"ошибка ии: {e}")
    
    # Fallback
    fallbacks = [
        f"{E_CAT_DANCE} {username}, я тут! хочешь сыграть? напиши 'энди кубик 100' {E_HEART}",
        f"{E_MAGIC} {username}, телепортнулась к тебе! на сервере сейчас {current_online}/{current_max} игроков, заходи! {E_JOYSTICK}",
        f"{E_HEART} {username}, не забывай про айпи: java 150.241.85.40:25565, бедрок 150.241.85.40:19132 {E_RABBIT}",
        f"{E_CROWN} {username}, на мирный режим нужна заявка через бота, а на smp можно сразу! {E_HOUSE}"
    ]
    
    response = random.choice(fallbacks)
    if not already_greeted and not is_reply:
        mark_greeted(username)
    
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
