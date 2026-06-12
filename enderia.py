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

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

# ========== НАСТРОЙКИ ФАЙЛОВОЙ ПАМЯТИ ЧАТА ==========
HISTORY_DIR = "chat_history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "chat.log")
MAX_HISTORY_LINES = 1000

# Создаём папку если её нет
try:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    print(f"✅ Папка {HISTORY_DIR} создана/существует")
except Exception as e:
    print(f"❌ Ошибка создания папки: {e}")

# Если файла нет - создаём
if not os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write(f"# История чата LostEarth\n# Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        print(f"✅ Файл {HISTORY_FILE} создан")
    except Exception as e:
        print(f"❌ Ошибка создания файла: {e}")
else:
    print(f"✅ Файл {HISTORY_FILE} уже существует")

def add_to_chat_memory(username: str, message: str, is_bot: bool = False):
    """Добавляет сообщение в файл истории чата"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🤖 Эндерия" if is_bot else f"👤 {username}"
        line = f"[{timestamp}] {prefix}: {message}\n"
        
        # Отладочный вывод
        print(f"💾 Сохраняю в чат-лог: {line[:100]}...")
        
        # Читаем существующие строки
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Добавляем новую строку
        lines.append(line)
        
        # Оставляем только последние MAX_HISTORY_LINES строк
        if len(lines) > MAX_HISTORY_LINES:
            header = lines[:2] if lines and lines[0].startswith("#") else []
            body = lines[2:] if header else lines
            lines = header + body[-MAX_HISTORY_LINES:]
        
        # Записываем обратно
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        
        print(f"✅ Сохранено, всего строк: {len(lines)}")
            
    except Exception as e:
        print(f"❌ Ошибка сохранения истории: {e}")

def get_chat_history(limit: int = 50) -> str:
    """Возвращает последние N сообщений из истории чата"""
    try:
        if not os.path.exists(HISTORY_FILE):
            print(f"⚠️ Файл {HISTORY_FILE} не существует")
            return ""
        
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        print(f"📖 Читаю историю чата, всего строк: {len(lines)}")
        
        # Пропускаем заголовки (строки начинающиеся с #)
        messages = [l.strip() for l in lines if not l.startswith("#") and l.strip()]
        
        # Берём последние limit сообщений
        last_messages = messages[-limit:] if len(messages) > limit else messages
        
        if not last_messages:
            return ""
        
        return "\n".join(last_messages)
        
    except Exception as e:
        print(f"❌ Ошибка чтения истории: {e}")
        return ""

def get_chat_context(limit: int = 30) -> str:
    """Возвращает контекст чата для Эндерии"""
    history = get_chat_history(limit)
    if not history:
        return ""
    
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 ИСТОРИЯ ЧАТА (последние сообщения):

{history}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ВАЖНО: Прочитай всю историю чата выше. Ты видишь, что пишут игроки. 
Отвечай естественно, как участник чата. Учитывай контекст разговора.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    greetings = ["привет", "здравствуй", "здарова", "хай", "hello", "hi", "privet", 
                 "доброе утро", "добрый день", "добрый вечер", "приветик"]
    return any(g in text_lower for g in greetings)

# ========== FALLBACK ОТВЕТЫ (ЕСЛИ ВСЕ МОДЕЛИ НЕ ОТВЕТЯТ) ==========
FALLBACK_ANSWERS_LIST = [
    "💜 {username}, связь с Краем потеряна! Повтори позже 🐱",
    "🐱 {username}, на LostEarth есть два режима: Мирный (PvP по согласию) и SMP (можно рейдить)! 🐰",
    "🐰 {username}, IP Java: 150.241.85.40:25565, Bedrock: 19132. Заходи играть! 💜",
    "💜 {username}, донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽ (полёт!), Архонт 400₽, Серафим 600₽. Пиши @pelmewki379 🐱",
    "🐱 {username}, админ: @pelmewki379, пиши по любым вопросам! 💜",
]

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
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False) -> str:
    global current_online, current_max
    
    # Сохраняем сообщение пользователя в лог
    add_to_chat_memory(username, user_message, is_bot=False)
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    user_ctx = get_user_context(username)
    chat_ctx = get_chat_context(limit=30)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Ограничение по времени
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
        add_to_chat_memory(username, response, is_bot=True)
        return response
    
    # Определяем инструкцию по приветствию
    if is_reply:
        greeting_instruction = "Ты отвечаешь на сообщение игрока. НЕ ЗДОРОВАЙСЯ! Продолжай диалог."
    elif already_greeted:
        greeting_instruction = "Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    else:
        greeting_instruction = "Ты ещё не здоровалась. Можешь поздороваться коротко."
    
    # Формируем полный промпт
    full_prompt = f"""{greeting_instruction}

{user_ctx}

{chat_ctx}

Игрок {username} написал: {user_message}
Это ответ на сообщение бота: {"ДА" if is_reply else "НЕТ"}

Отвечай как Эндерия (2-4 предложения). Будь естественной.
НЕ используй HTML теги. ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
В конце поставь 1-2 эмодзи."""

    system_prompt = get_system_prompt(username, current_time, current_online, current_max)
    
    # Проверяем наличие API ключа
    if not OPENROUTER_API_KEY:
        print("❌ НЕТ OPENROUTER_API_KEY! Использую fallback ответы.")
        fallback = random.choice(FALLBACK_ANSWERS_LIST).format(username=username)
        add_to_memory(username, user_message, fallback)
        add_to_chat_memory(username, fallback, is_bot=True)
        return fallback
    
    # Пробуем модели по очереди
    for model_index, model in enumerate(MODELS_CHAIN):
        print(f"🔄 [{model_index + 1}/{len(MODELS_CHAIN)}] Пробуем {model}")
        
        result, success = await ask_model(model, system_prompt, full_prompt)
        
        if success and result and len(result) > 10:
            has_russian = any(ord(c) > 1024 for c in result)
            if not has_russian:
                print(f"⚠️ Модель {model} ответила не на русском, пробуем дальше")
                continue
                
            print(f"✅ УСПЕХ! Модель {model} ответила по-русски!")
            
            result = re.sub(r'<[^>]+>', '', result)
            
            if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                result += f" {get_enderia_emojis()}"
            
            if not already_greeted and not is_reply:
                mark_greeted(username)
            
            add_to_memory(username, user_message, result)
            add_to_chat_memory(username, result, is_bot=True)
            
            return result
        
        await asyncio.sleep(0.3)
    
    # Если все модели не ответили
    print("❌ Все модели не ответили! Использую fallback ответы.")
    emojis = get_enderia_emojis()
    fallback = random.choice(FALLBACK_ANSWERS_LIST).format(username=username)
    fallback = f"{emojis} {fallback}"
    add_to_memory(username, user_message, fallback)
    add_to_chat_memory(username, fallback, is_bot=True)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
