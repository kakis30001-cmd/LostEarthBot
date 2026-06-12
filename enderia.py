import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

# Импортируем всё из prompts.py
from prompts import (
    get_system_prompt, 
    get_enderia_emojis, 
    FALLBACK_RESPONSES,
    ENDERIA_EMOJI
)

load_dotenv()

# ========== OPENROUTER НАСТРОЙКИ ==========
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ТОП-5 МОДЕЛЕЙ С ЛУЧШИМ РУССКИМ ЯЗЫКОМ
MODELS_CHAIN = [
    "openai/gpt-oss-120b",                    # 1. OpenAI, лучший русский
    "nousresearch/hermes-3-405b-instruct",    # 2. 405B, очень умная
    "meta-llama/llama-3.3-70b-instruct",      # 3. 70B, стабильный
    "qwen/qwen3-next-80b-a3b-instruct",       # 4. Qwen от Alibaba
    "nvidia/nemotron-3-nano-30b-a3b",         # 5. NVIDIA, быстрая
]

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_last_question = {}
user_greeted = {}
user_last_time = {}

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    context = "\n".join(list(user_memory[username]))
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📜 ИСТОРИЯ ДИАЛОГА С {username}:
{context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ВАЖНО: Продолжай диалог логично! НЕ ЗДОРОВАЙСЯ, если уже здоровались!
"""

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = False
    if username in user_last_question:
        user_last_question[username] = None

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def has_already_greeted(username: str) -> bool:
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    user_greeted[username] = True

def is_greeting(text: str) -> bool:
    text_lower = text.lower()
    greetings = ["привет", "здравствуй", "здарова", "хай", "hello", "hi", "privet"]
    return any(g in text_lower for g in greetings)

# ========== ЗАПРОС К МОДЕЛИ ==========
async def ask_model(model: str, system_prompt: str, user_prompt: str) -> tuple[str, bool]:
    """Отправляет запрос к модели. Возвращает (ответ, успех)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://t.me/LostEarthBot",
                    "X-Title": "LostEarth Bot"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 250,
                    "temperature": 0.9,
                    "top_p": 0.95,
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    result = data["choices"][0]["message"]["content"].strip()
                    return result, True
                else:
                    print(f"❌ Модель {model} ошибка {response.status}")
                    return "", False
                    
    except asyncio.TimeoutError:
        print(f"⏰ Модель {model} таймаут")
        return "", False
    except Exception as e:
        print(f"⚠️ Модель {model} ошибка: {e}")
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с переключением между топ-5 моделями"""
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    context = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Ограничение по времени (не чаще чем раз в 2 секунды)
    now = datetime.now().timestamp()
    last_time = user_last_time.get(username, 0)
    if now - last_time < 2:
        await asyncio.sleep(1)
    user_last_time[username] = now
    
    # Если уже здоровались и это снова приветствие
    if already_greeted and is_greeting_msg:
        emojis = get_enderia_emojis()
        response = f"{emojis} {username}, ты уже здоровался! Что хотел узнать про LostEarth?"
        add_to_memory(username, user_message, response)
        return response
    
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = "Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    
    full_prompt = f"""{greeting_instruction}
{context}

Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). В конце ответа поставь эмодзи (🐱💜🐰). Не используй HTML теги! ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ!"""

    system_prompt = get_system_prompt(username, current_time)
    
    # Пробуем модели по очереди
    for model_index, model in enumerate(MODELS_CHAIN):
        print(f"🔄 [{model_index + 1}/{len(MODELS_CHAIN)}] Пробуем {model}")
        
        result, success = await ask_model(model, system_prompt, full_prompt)
        
        if success and result and len(result) > 10:
            # Проверяем, что ответ на русском
            has_russian = any(ord(c) > 1024 for c in result)
            if not has_russian:
                print(f"⚠️ Модель {model} ответила не на русском, пробуем дальше")
                continue
                
            print(f"✅ УСПЕХ! Модель {model} ответила по-русски!")
            
            # Убираем все HTML теги
            result = re.sub(r'<[^>]+>', '', result)
            
            # Добавляем эмодзи если их нет
            if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                result += f" {get_enderia_emojis()}"
            
            # Отмечаем что поздоровались
            if not already_greeted:
                mark_greeted(username)
            
            add_to_memory(username, user_message, result)
            return result
        
        await asyncio.sleep(0.3)
    
    # Если все модели не ответили
    print("❌ Все модели не ответили!")
    emojis = get_enderia_emojis()
    fallback = random.choice(FALLBACK_RESPONSES).format(emojis=emojis, username=username)
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
