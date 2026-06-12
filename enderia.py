import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

from prompts import get_system_prompt, get_enderia_emojis, FALLBACK_RESPONSES, ENDERIA_EMOJI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-oss-120b",
    "nousresearch/hermes-3-405b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "nvidia/nemotron-3-nano-30b-a3b",
]

# ========== ГЛОБАЛЬНАЯ ПАМЯТЬ ЧАТА (последние 15 сообщений) ==========
chat_memory = deque(maxlen=15)
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

def add_to_chat_memory(username: str, message: str):
    """Добавляет сообщение в общую память чата"""
    chat_memory.append(f"{username}: {message}")
    print(f"[ЧАТ] {username}: {message[:50]}...")

def get_chat_context() -> str:
    """Возвращает контекст последних 15 сообщений чата"""
    if not chat_memory:
        return ""
    result = "\n".join(list(chat_memory))
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 ПОСЛЕДНИЕ СООБЩЕНИЯ В ЧАТЕ:
{result}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Прочитай эти сообщения, чтобы понять контекст разговора. Если кто-то спрашивал про тебя или сервер - учти это!
"""

# ========== ПАМЯТЬ ДИАЛОГОВ С КАЖДЫМ ПОЛЬЗОВАТЕЛЕМ ==========
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
    greetings = ["привет", "здравствуй", "здарова", "хай", "hello", "hi", "privet", "доброе утро", "добрый день", "добрый вечер"]
    return any(g in text_lower for g in greetings)

# ========== ЗАПРОС К МОДЕЛИ ==========
async def ask_model(model: str, system_prompt: str, user_prompt: str) -> tuple[str, bool]:
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
                    "max_tokens": 300,
                    "temperature": 0.9,
                    "top_p": 0.95,
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=35)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data["choices"][0]["message"]["content"].strip()
                    return result, True
                else:
                    error_text = await response.text()
                    print(f"❌ Модель {model} ошибка {response.status}: {error_text[:100]}")
                    return "", False
    except asyncio.TimeoutError:
        print(f"⏰ Модель {model} таймаут")
        return "", False
    except Exception as e:
        print(f"⚠️ Модель {model} ошибка: {e}")
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_context: str = "") -> str:
    global current_online, current_max
    
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
    
    # Если уже здоровались и это снова приветствие (и не ответ на сообщение)
    if already_greeted and is_greeting_msg and not is_reply:
        emojis = get_enderia_emojis()
        response = f"{emojis} {username}, мы уже общаемся! Что хотел узнать про LostEarth? 💜"
        add_to_memory(username, user_message, response)
        return response
    
    # Определяем инструкцию по приветствию
    if is_reply:
        greeting_instruction = "Ты отвечаешь на сообщение игрока. НЕ ЗДОРОВАЙСЯ! Продолжай диалог, отвечай по существу."
    elif already_greeted:
        greeting_instruction = "Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    else:
        greeting_instruction = "Ты ещё не здоровалась. Можешь поздороваться один раз, но коротко."
    
    # Формируем полный промпт
    full_prompt = f"""{greeting_instruction}

{context}

{chat_context}

Игрок {username} написал: {user_message}
Это ответ на сообщение бота: {"ДА" if is_reply else "НЕТ"}

Ответь как Эндерия (2-4 предложения). 
- Если это ответ на твоё сообщение - ПРОДОЛЖАЙ РАЗГОВОР, не начинай заново
- Если игрок задал вопрос про сервер - ответь и в конце добавь "кстати, всю информацию можно посмотреть командой /start"
- НЕ ИСПОЛЬЗУЙ матерные слова
- НЕ ОСКОРБЛЯЙ никого
- Будь вежливой и дружелюбной
- Если спрашивают про ЛГБТ или политику - скажи "я нейтральна, я просто игровой помощник"
- В конце ответа поставь 1-2 эмодзи
- Не используй HTML теги
- ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ"""

    system_prompt = get_system_prompt(username, current_time, current_online, current_max)
    
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
            
            # Отмечаем что поздоровались (если не ответ на сообщение)
            if not already_greeted and not is_reply:
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
