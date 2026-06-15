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

# ========== ССЫЛКИ ==========
RULES_URL = "https://lostearthbot-production.up.railway.app/rules.html"
DONATE_URL = "https://lostearthbot-production.up.railway.app/donate.html"
APPLY_URL = "https://lostearthbot-production.up.railway.app/apply.html"

# ========== РАБОЧИЕ БЕСПЛАТНЫЕ МОДЕЛИ ==========
MODELS_CHAIN = [
    "qwen/qwen-2.5-72b-instruct",
    "google/gemini-2.0-flash-exp",
    "microsoft/phi-3.5-mini-instruct",
    "meta-llama/llama-3.2-3b-instruct",
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
user_memory = defaultdict(lambda: deque(maxlen=350))
user_last_greet = {}
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str, limit: int = 25) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    messages = list(user_memory[username])[-limit*2:]
    return "\n".join(messages)

def get_full_history(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username]))

def get_last_bot_response(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return user_memory[username][-1].replace("bot: ", "")

def get_last_user_message(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) < 2:
        return ""
    return user_memory[username][-2].replace("user: ", "")

def can_greet(username: str) -> bool:
    if username not in user_last_greet:
        return True
    last = user_last_greet[username]
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    return datetime.now() - last > timedelta(hours=12)

def mark_greeted(username: str):
    user_last_greet[username] = datetime.now().isoformat()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "ку", "доброе", "салам"]
    return any(g in text.lower() for g in greetings)

def is_game_command(text: str) -> bool:
    text_lower = text.lower()
    game_keywords = ["кубик", "футбол", "плюнуть", "фарма", "улучши", "слоты", "пай"]
    return any(keyword in text_lower for keyword in game_keywords)

def is_just_name_call(text: str) -> bool:
    text_lower = text.lower().strip()
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    
    if is_game_command(text):
        return False
    
    names = ["энди", "енди", "энд"]
    return clean_text in names or clean_text == "энд"

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["энди", "енди", "энд"]
    return any(keyword in text_lower for keyword in keywords)

# ========== РАСПОЗНАВАНИЕ ЗАПРОСОВ ==========
def is_rules_request(text: str) -> bool:
    text_lower = text.lower()
    rules_keywords = [
        "правил", "правила", "правило", "правела", "правело",
        "какие правила", "что за правила", "расскажи правила",
        "покажи правила", "скинь правила", "дай правила",
        "правила сервера", "сервер правила", "какие тут правила"
    ]
    return any(keyword in text_lower for keyword in rules_keywords)

def is_apply_request(text: str) -> bool:
    text_lower = text.lower()
    apply_keywords = [
        "заявк", "как подать", "подать заявку", "как зайти",
        "мирный режим", "как попасть", "заявка на мирный",
        "как играть", "как начать играть"
    ]
    return any(keyword in text_lower for keyword in apply_keywords)

def is_donate_request(text: str) -> bool:
    text_lower = text.lower()
    donate_keywords = [
        "донат", "донаты", "купить", "премиум", 
        "сколько стоит", "цены", "прайс", "привилегия",
        "как купить", "хочу купить", "донат на сервер",
        "привилегии", "руб", "грн", "донатик", "пожертв"
    ]
    return any(keyword in text_lower for keyword in donate_keywords)

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
    
    if game_result:
        return None
    
    if is_game_command(user_message):
        print(f"🎮 Игровая команда, пропускаем: {user_message}")
        return None
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name_call(user_message)
    can_say_greet = can_greet(username)
    
    # Просто имя "Энди"
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username}! Напиши 'энди кубик 100' чтобы сыграть {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Приветствие
    if is_greeting_msg and can_say_greet and not is_reply:
        mark_greeted(username)
        response = f"{E_CAT_DANCE} привет, {username}! Хочешь сыграть? Напиши 'энди кубик 100' {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    user_lower = user_message.lower().strip()
    
    # ========== ИНФОРМАЦИЯ О БУНКЕРЕ (БЕЗ ПЕРЕХВАТА КОМАНДЫ "энди бункер") ==========
    
    # Вопрос "как играть в бункер"
    if "как играть" in user_lower and "бункер" in user_lower:
        response = f"""{E_MAGIC} <b>правила игры "бункер"</b> {E_MAGIC}

1️⃣ <b>начало:</b> напиши <code>энди бункер</code> чтобы создать лобби
2️⃣ <b>сбор игроков:</b> нужно от 3 до 12 человек
3️⃣ <b>получение ролей:</b> каждому придёт СЕКРЕТНАЯ роль в личку!
4️⃣ <b>суть игры:</b> нужно убедить других, что ты полезен
5️⃣ <b>голосование:</b> каждый раунд выбираем кого выгнать
6️⃣ <b>победа:</b> последние 2-3 выживших получают +100 XP

готов начать? напиши <code>энди бункер</code>! {E_HEART}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Вопрос "что такое бункер"
    if ("бункер" in user_lower and "энди" not in user_lower) or user_lower == "что такое бункер":
        response = f"""{E_HOUSE} <b>бункер</b> - игра на выживание в зомби апокалипсисе! 🧟

<b>как начать:</b> напиши <code>энди бункер</code>
<b>награда:</b> победители +100 XP!

хочешь попробовать? {E_CAT_DANCE}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Вопрос "правила бункера"
    if "правила бункера" in user_lower or "правило бункера" in user_lower:
        response = f"""{E_NOTE} <b>правила игры "бункер"</b> {E_NOTE}
• не показывай свою роль другим!
• убеждай что ты полезен
• не голосовать = вылетаешь автоматически
• выгнали = -50 XP
• победители = +100 XP

напиши <code>энди бункер</code> чтобы начать! {E_HEART}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # ========== ПРОВЕРКА НА ПРАВИЛА ==========
    if is_rules_request(user_message):
        response = f"""{E_NOTE} <b>правила сервера lostearth</b> {E_NOTE}

вот ссылка на правила:
👉 <a href="{RULES_URL}">ПРАВИЛА СЕРВЕРА</a>

ознакомься перед игрой, там ничего сложного! {E_CAT_OK}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # ========== ПРОВЕРКА НА ЗАЯВКУ ==========
    if is_apply_request(user_message):
        response = f"""{E_MAGIC} <b>заявка на мирный режим</b> {E_MAGIC}

хочешь играть без гриферства? подавай заявку!

👉 <a href="{APPLY_URL}">ПОДАТЬ ЗАЯВКУ</a>

после подачи заявки жди ответа администратора! {E_RABBIT}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # ========== ПРОВЕРКА НА ДОНАТЫ ==========
    if is_donate_request(user_message):
        response = f"""{E_CROWN} <b>донат на lostearth</b> {E_CROWN}

все цены и возможности здесь:
👉 <a href="{DONATE_URL}">ДОНАТЫ И ПРИВИЛЕГИИ</a>

{E_HEART} все деньги идут на хостинг!
по вопросам: @pelmewki379"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # ========== AI ОТВЕТ ==========
    if OPENROUTER_API_KEY:
        try:
            context = get_user_context(username, limit=25)
            
            system_prompt = f"""ты энди, девушка-эндермен. Ты помогаешь игрокам на сервере lostearth.

ТВОЙ ХАРАКТЕР:
- добрая, загадочная, слегка вредная
- любишь телепортироваться и играть с игроками
- пишешь с маленькой буквы
- используешь эмодзи в конце сообщений

ПРАВИЛА ОТВЕТОВ:
1. Если игрок пишет "нет" на предложение поиграть - не предлагай снова!
2. Отвечай по существу, не будь назойливой
3. Используй ласковые обращения: "игрок~", "дружок~", "зайка~"

ИСТОРИЯ ДИАЛОГА:
{context}

ИНФОРМАЦИЯ О СЕРВЕРЕ:
- IP: 150.241.85.40:25565
- Онлайн: {current_online}/{current_max}

СЕЙЧАС:
Игрок {username} написал: {user_message}

Ответь по-человечески, коротко (1-2 предложения), не повторяй то что уже говорила:"""
            
            async with aiohttp.ClientSession() as session:
                for model in MODELS_CHAIN:
                    try:
                        print(f"🔄 Пробую {model}...")
                        
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
                                "max_tokens": 200,
                                "temperature": 0.8,
                            },
                            timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                print(f"✅ Ответ от {model}")
                                
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                            else:
                                error = await resp.text()
                                print(f"❌ {model} ошибка {resp.status}: {error[:100]}")
                                continue
                                
                    except asyncio.TimeoutError:
                        print(f"⏰ Таймаут {model}")
                        continue
                    except Exception as e:
                        print(f"❌ Ошибка {model}: {e}")
                        continue
                        
        except Exception as e:
            print(f"❌ Общая ошибка AI: {e}")
    
    # Fallback ответы
    last_bot = get_last_bot_response(username)
    
    if "кубик" in last_bot or "сыграть" in last_bot:
        response = f"{E_CAT_OK} понял, {username}. Если захочешь сыграть - пиши 'энди кубик 100' {E_HEART}"
    else:
        response = f"{E_CAT_DANCE} {username}, я тут. Что хочешь узнать? Напиши /games для списка команд {E_HEART}"
    
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
