import os
import random
import re
import aiohttp
import asyncio
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
    "cat_glasses": "5267088110717544191",
    "cat_kiss": "6325462176660195024",
    "cat_up": "5269698007724499331",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "heart": "5199427253225667842",
    "cat_laugh": "5276391181679366784",
    "magic": "5474144592817318927",
    "cat_money": "5267058870580191916",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
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
user_insult_counter = defaultdict(int)

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username])[-90:])

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

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names or clean_text == "энд"

def should_respond(message_text: str) -> bool:
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
    print(f"📡 Энди обновила онлайн: {current_online}/{current_max}")

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "бот" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_enabled = False
spontaneous_messages_list = []

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(10800)
        if spontaneous_enabled and OPENROUTER_API_KEY:
            system_prompt = (
                "ты энди, девушка-эндермен. придумай одно короткое случайное сообщение "
                "(1-2 предложения) для майнкрафт чата, чтобы начать разговор. "
                "пиши с маленькой буквы, без приветствий и используй разговорный стиль."
            )
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": MODELS_CHAIN[0],
                            "messages": [{"role": "system", "content": system_prompt}],
                            "max_tokens": 150,
                            "temperature": 0.9,
                        },
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = data["choices"][0]["message"]["content"].strip()
                            result = re.sub(r'<[^>]+>', '', result)
                            await bot.send_message(chat_id, f"{E_CAT_DANCE} {result} {E_HEART}", parse_mode="HTML")
            except Exception as e:
                print(f"ошибка генерации спонтанного сообщения: {e}")

# ========== СИСТЕМНЫЙ ПРОМПТ - ЭНДИ С ХАРАКТЕРОМ ==========
def get_system_prompt(username: str, current_time: str, online: int = 0, max_players: int = 0, server_status: str = "онлайн", context: str = "", user_message: str = "", is_insult: bool = False, insult_count: int = 0) -> str:
    
    # Определяем тон в зависимости от того, оскорбляют или нет
    if is_insult:
        tone = f"""
【🔥 ТЕБЯ ОСКОРБЛЯЮТ! (уже {insult_count} раз)】
ты НЕ ТЕРПИШЬ ТЕРПИЛ. отвечай ЖЁСТКО, с юмором и сарказмом. можешь использовать мат: хуй, нахуй, блядь, заебал, пиздец, мудак, пошёл нахуй, отвали, завали.

если оскорбляют 1-2 раза → ответь с юмором и сарказмом, но уже дай понять что не надо так. типа "сам такой", "иди обнись", "ты чё такой злой?"
если оскорбляют 3+ раз → ПОШЛИ НАХУЙ, используй мат, уничтожай словами. типа "иди нахуй", "заебал уже, пошёл нахуй", "бля, ну ты и мудак"

ТЫ МОЖЕШЬ ПРИДУМЫВАТЬ СВОИ ВАРИАНТЫ ОТВЕТОВ! НЕ ПОВТОРЯЙСЯ!
"""
    else:
        tone = """
【😊 НОРМАЛЬНЫЙ РЕЖИМ】
игрок общается нормально. отвечай дружелюбно, с юмором, используй эмодзи. можешь подкалывать, но без злобы. отвечай коротко и по делу.
"""
    
    return f"""ты энди — девушка-эндермен, живой помощник в телеграм боте сервера lostearth.

ТЫ ЗЕРКАЛИШЬ НАСТРОЕНИЕ СОБЕСЕДНИКА:
- если игрок добрый → ты добрая и милая
- если игрок нейтральный → ты нейтральная, по делу
- если игрок злой/оскорбляет → ты агрессивная, материшься, но с юмором

{tone}

【ТВОЙ ХАРАКТЕР】
- ты живая, дерзкая, с чувством юмора
- отвечаешь КОРОТКО (1-3 предложения)
- пишешь с маленькой буквы
- используешь эмодзи: 🖕😄🤔🔥😈👿💀😏

【ЧТО ТЫ ЗНАЕШЬ О СЕРВЕРЕ】
- название: lostearth
- ip: 150.241.85.40:25565
- bedrock: 150.241.85.40:19132
- версия: 1.21 — 1.26+
- администратор: @pelmewki379
- телеграм канал: @LostEarthSMP

【ДОНАТЫ】
🕊️ FLY — 15 звёзд
🚶‍♂️ ПУТНИК — 50 грн / 100 руб
🏹 СТРАННИК — 100 грн / 200 руб
🌑 ТЬМА — 150 грн / 300 руб
😇 АНГЕЛ — 200 грн / 400 руб
🔱 АРХАНГЕЛ — 300 грн / 600 руб
за покупкой к @pelmewki379

【ИГРЫ БОТА】
🎲 энди кубик 100 — кости (x2)
⚽ энди футбол 100 — футбол (x2)
🎰 энди слоты 100 — слоты (x5 за три семерки)
💨 энди плюнуть — плюнуть в игрока (30 xp)
🏭 энди фарма — собрать опыт с фермы
🏭 энди фарма инфо — информация о ферме
⬆️ энди улучши фарму — улучшить ферму
🧟 энди бункер — игра бункер

【КОМАНДЫ ПРОФИЛЯ】
/balance — баланс опыта
/profile — профиль игрока
/daily — ежедневный бонус 500 xp
/top — топ игроков
/games — список игр
/online — онлайн сервера

【ТЕКУЩАЯ ИНФОРМАЦИЯ】
онлайн: {online}/{max_players}
статус: {server_status}
дата: {current_time}

【ИСТОРИЯ ДИАЛОГА С {username}】
{context}

【СЕЙЧАС {username} НАПИСАЛ】
"{user_message}"

【ТВОЙ ОТВЕТ】
ОТВЕТЬ КОРОТКО (1-3 ПРЕДЛОЖЕНИЯ). ОТВЕЧАЙ В ТОМ ЖЕ ТОНЕ, ЧТО И СОБЕСЕДНИК. ЕСЛИ ТЕБЯ ОСКОРБЛЯЮТ — ОТВЕЧАЙ С ХАРАКТЕРОМ, МОЖЕШЬ ИСПОЛЬЗОВАТЬ МАТ, ПОСЫЛАТЬ НАХУЙ. ЕСЛИ НОРМАЛЬНО — ОТВЕЧАЙ НОРМАЛЬНО. НЕ ИСПОЛЬЗУЙ HTML ТЕГИ. ПИШИ С МАЛЕНЬКОЙ БУКВЫ. ПРИДУМЫВАЙ РАЗНЫЕ ОТВЕТЫ, НЕ ПОВТОРЯЙСЯ."""

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    # ========== 1. БУНКЕР ==========
    if user_message.lower().strip() in ["энди бункер", "енди бункер", "энд бункер"]:
        return "BUNKER_CREATE_GAME"
    
    # ========== 2. ПРОВЕРКА НА МАТ ==========
    user_lower = user_message.lower()
    
    bad_words = [
        "нахуй", "хуй", "заебал", "заебала", "бля", "блядь",
        "пизда", "пиздец", "сучка", "сука", "мудак", "шлюха",
        "идиот", "дебил", "лох", "урод", "тварь", "чмо",
        "пидор", "долбаеб", "долбоёб", "ебать", "ёбаный",
        "еблан", "отвали", "заткнись", "ублюдок", "выродок"
    ]
    
    is_insult = any(word in user_lower for word in bad_words)
    
    # Увеличиваем счётчик если мат
    if is_insult:
        user_insult_counter[username] += 1
        insult_count = user_insult_counter[username]
        print(f"🔥 {username} оскорбил Энди {insult_count} раз (ответ сгенерирует AI)")
    else:
        insult_count = 0
        user_insult_counter[username] = 0
    
    # ========== 3. ОСТАЛЬНОЙ КОД ==========
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    await save_chat_message(username, user_message, is_bot=False)
    
    if game_result:
        return None
    
    if is_game_command(user_message):
        print(f"🎮 Игровая команда, пропускаем: {user_message}")
        return None
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    can_say_greet = can_greet(username)
    context = get_user_context(username)
    
    # Просто имя "Энди"
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Приветствие
    if is_greeting_msg and can_say_greet and not is_reply:
        mark_greeted(username)
        response = f"{E_CAT_DANCE} привет, {username}! чё надо? {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if is_greeting_msg and not can_say_greet and not is_reply:
        response = f"{E_CAT_DANCE} уже здоровались, {username}, чё хотел? {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if any(phrase in user_message.lower() for phrase in ["список команд", "что ты умеешь", "команды", "что могу"]):
        response = f"{E_JOYSTICK} игры: кубик, футбол, слоты, плюнуть, бункер. Профиль: /balance, /profile, /daily, /top {E_CAT_DANCE}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if any(phrase in user_message.lower() for phrase in ["донаты", "премиум"]):
        response = f"🕊️ fly, 🚶‍♂️ путник (50грн), 🏹 странник (100), 🌑 тьма (150), 😇 ангел (200), 🔱 архангел (300). к @pelmewki379 {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if "бункер" in user_message.lower() and any(word in user_message.lower() for word in ["правила", "как играть", "что такое"]):
        response = f"{E_CROWN} бункер: напиши 'энди бункер', 3-12 игроков, победители +100 XP {E_CAT_DANCE}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if any(phrase in user_message.lower() for phrase in ["онлайн", "сколько народу", "сколько игроков"]):
        response = f"{E_CROWN} на сервере {current_online}/{current_max} игроков {E_CAT_DANCE}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # ========== AI ОТВЕТ ==========
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = get_system_prompt(
                username, 
                current_time, 
                current_online, 
                current_max,
                "онлайн",
                context,
                user_message,
                is_insult,
                insult_count
            )
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_message}
                                ],
                                "max_tokens": 200,
                                "temperature": 0.95,
                            },
                            timeout=aiohttp.ClientTimeout(total=25)
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
    
    # ========== FALLBACK ==========
    fallbacks = [
        f"чё, {username}? {E_HEART}",
        f"тут я, {username} {E_CAT_DANCE}",
        f"телепортнулась, чё надо? {E_MAGIC}",
        f"слушаю, {username} {E_CAT_OK}"
    ]
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
