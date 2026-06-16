import o
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

# ========== СИСТЕМНЫЙ ПРОМПТ ==========
def get_system_prompt(username: str, current_time: str, online: int = 0, max_players: int = 0, server_status: str = "онлайн", context: str = "") -> str:
    return f"""ты энди — девушка-эндермен, живой помощник в телеграм боте.

ТЫ ЗЕРКАЛИШЬ НАСТРОЕНИЕ СОБЕСЕДНИКА:
- если игрок добрый → ты добрая и милая
- если игрок нейтральный → ты нейтральная, по делу
- если игрок злой/оскорбляет → ты агрессивная, материшься

ОТВЕЧАЙ КОРОТКО (1-3 предложения), с маленькой буквы, используй эмодзи.

Ты знаешь:
- сервер lostearth, ip: 150.241.85.40:25565, админ @pelmewki379
- донаты: fly (15 звёзд), путник (50грн), странник (100), тьма (150), ангел (200), архангел (300)
- игры: кубик, футбол, слоты, плюнуть, бункер
- команды: /balance, /profile, /daily, /top

онлайн: {online}/{max_players}

история диалога:
{context}

сейчас {username} написал: {user_message}

ответь коротко, по-человечески, отражая настроение собеседника."""

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    # ========== 1. КОМАНДА БУНКЕРА ==========
    if user_message.lower().strip() in ["энди бункер", "енди бункер", "энд бункер"]:
        return "BUNKER_CREATE_GAME"
    
    # ========== 2. ПРОВЕРКА НА МАТ (САМАЯ ПЕРВАЯ!) ==========
    user_lower = user_message.lower()
    is_bad = any([
        "нахуй" in user_lower or "на хую" in user_lower,
        "иди" in user_lower and "нахуй" in user_lower,
        "пошла" in user_lower and "нахуй" in user_lower,
        "пошёл" in user_lower and "нахуй" in user_lower,
        "заебал" in user_lower, "заебала" in user_lower, "заебали" in user_lower,
        "сучка" in user_lower, "шлюха" in user_lower,
        "мудак" in user_lower, "пизда" in user_lower, "пиздец" in user_lower,
        "блядь" in user_lower, "бля" in user_lower,
        "хуй" in user_lower, "хуесос" in user_lower, "хуя" in user_lower,
        "ублюдок" in user_lower, "тварь" in user_lower,
        "нахуц" in user_lower, "нах" in user_lower,
        "иднх" in user_lower, "пнх" in user_lower,
        "соси" in user_lower, "отсоси" in user_lower,
        "завали" in user_lower, "заткнись" in user_lower, "закройся" in user_lower,
        "долбаеб" in user_lower, "долбоёб" in user_lower,
        "придурок" in user_lower, "идиот" in user_lower, "дебил" in user_lower,
        "козел" in user_lower, "олень" in user_lower,
        "терпила" in user_lower, "лох" in user_lower,
        "урод" in user_lower, "чмо" in user_lower,
        "ебать" in user_lower, "ёбаный" in user_lower, "ебаный" in user_lower,
        "еблан" in user_lower, "пидор" in user_lower,
        "сука" in user_lower, "сукин" in user_lower,
        "отвали" in user_lower, "отъебись" in user_lower,
        "проваливай" in user_lower, "сдохни" in user_lower,
        "тварь" in user_lower, "выродок" in user_lower,
    ])
    
    if is_bad:
        user_insult_counter[username] += 1
        count = user_insult_counter[username]
        
        print(f"🔥 {username} оскорбил Энди {count} раз")  # Отладка
        
        if count >= 3:
            response = random.choice([
                f"иди нахуй, {username} 🖕",
                f"заебал уже, пошёл нахуй",
                f"бля, ну ты и мудак, {username}",
                f"пошёл нахуй, я не терпила",
                f"отвали, надоел уже, иди нахуй"
            ])
            add_to_memory(username, user_message, response)
            await save_chat_message(username, response, is_bot=True)
            await save_andy_dialog(username, user_message, response)
            return response
        elif count == 2:
            response = random.choice([
                f"не беси меня, {username}",
                f"сам такой, {username} 🖕",
                f"я конечно добрая, но не до такой степени"
            ])
            add_to_memory(username, user_message, response)
            await save_chat_message(username, response, is_bot=True)
            await save_andy_dialog(username, user_message, response)
            return response
        else:
            response = random.choice([
                f"сам такой, {username} 🖕",
                f"иди обнись, {username}",
                f"ты чё такой злой? 😄"
            ])
            add_to_memory(username, user_message, response)
            await save_chat_message(username, response, is_bot=True)
            await save_andy_dialog(username, user_message, response)
            return response
    
    # Если не мат - сбрасываем счётчик
    if not is_bad:
        user_insult_counter[username] = 0
    
    # ========== 3. ОСТАЛЬНОЙ КОД ==========
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    await save_chat_message(username, user_message, is_bot=False)
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    can_say_greet = can_greet(username)
    context = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    # Если просто имя
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
    
    # Повторное приветствие
    if is_greeting_msg and not can_say_greet and not is_reply:
        response = f"{E_CAT_DANCE} уже здоровались, {username}, чё хотел? {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Список команд
    if any(phrase in user_message.lower() for phrase in ["список команд", "что ты умеешь", "команды", "что могу"]):
        response = f"""{E_JOYSTICK} вот что я умею:

🎮 игры: кубик, футбол, слоты, плюнуть
🏭 ферма: фарма, фарма инфо, улучши
🧟 бункер: энди бункер
📊 профиль: /balance, /profile, /daily, /top

во что сыграем? {E_CAT_DANCE}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Донаты
    if any(phrase in user_message.lower() for phrase in ["донаты", "премиум", "что дают за донат", "какие донаты", "сколько стоят донаты"]):
        response = f"""🕊️ fly — 15 звёзд
🚶‍♂️ путник — 50 грн
🏹 странник — 100 грн
🌑 тьма — 150 грн
😇 ангел — 200 грн
🔱 архангел — 300 грн

к @pelmewki379 {E_HEART}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response

    # Бункер
    if any(phrase in user_message.lower() for phrase in [
        "бункер правила", "правила бункера", "как играть в бункер",
        "что такое бункер", "бункер игра"
    ]):
        response = f"{E_CROWN} бункер: напиши 'энди бункер', 3-12 игроков, победители +100 XP {E_CAT_DANCE}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Онлайн
    if any(phrase in user_message.lower() for phrase in ["онлайн", "сколько народу", "сколько игроков"]):
        response = f"{E_CROWN} на сервере {current_online}/{current_max} игроков {E_CAT_DANCE}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # AI ответ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = get_system_prompt(
                username, 
                current_time, 
                current_online, 
                current_max,
                "онлайн",
                context
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
    
    # Fallback
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
