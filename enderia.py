import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

from prompts import get_system_prompt, get_enderia_emojis, ENDERIA_EMOJI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-oss-120b",
    "nousresearch/hermes-3-405b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "nvidia/nemotron-3-nano-30b-a3b",
]

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

# ========== ПРОСТАЯ ЗАПИСЬ В ЛОГ ==========
LOG_FILE = "chat.log"

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
        print(f"📝 Лог: [{timestamp}] {who}: {message[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка лога: {e}")

def get_last_messages(limit: int = 20) -> str:
    try:
        if not os.path.exists(LOG_FILE):
            return ""
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-limit:])
    except:
        return ""

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_greeted = {}
user_last_time = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

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
    text_lower = text.lower()
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text_lower for g in greetings)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False) -> str:
    global current_online, current_max
    
    print(f"🔍 Эндерия вызвана: {username} написал '{user_message}'")
    save_to_log(username, user_message, is_bot=False)
    
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Если уже здоровались и снова привет
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"💜 {username}, мы уже общаемся! Что хотел узнать про LostEarth? 🐱"
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Пытаемся получить ответ от ИИ
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        system_prompt = get_system_prompt(username, current_time, current_online, current_max)
        
        full_prompt = f"""Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). Будь милой и дружелюбной. В конце поставь 1-2 эмодзи."""
        
        for model in MODELS_CHAIN:
            try:
                print(f"🔄 Пробуем модель {model}")
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": full_prompt}
                            ],
                            "max_tokens": 200,
                            "temperature": 0.85,
                        },
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = data["choices"][0]["message"]["content"].strip()
                            result = re.sub(r'<[^>]+>', '', result)
                            
                            if not already_greeted:
                                mark_greeted(username)
                            
                            add_to_memory(username, user_message, result)
                            save_to_log(username, result, is_bot=True)
                            print(f"✅ Ответ от {model}")
                            return result
            except Exception as e:
                print(f"❌ Ошибка модели {model}: {e}")
                continue
            
            await asyncio.sleep(0.3)
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
    
    # Fallback ответы
    fallbacks = [
        f"💜 {username}, я Эндерия! На LostEarth есть два режима: Мирный (PvP по согласию) и SMP (можно рейдить)! 🐱",
        f"🐱 {username}, IP Java: 150.241.85.40:25565, Bedrock порт 19132. Заходи играть! 🐰",
        f"💜 {username}, донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽ (полёт!), Архонт 400₽, Серафим 600₽. Пиши @pelmewki379 🐱",
        f"🐰 {username}, привет! Я Эндерия, хранительница Края. Чем могу помочь? 💜",
    ]
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
