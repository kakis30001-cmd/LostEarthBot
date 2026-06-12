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
# Используем абсолютный путь для Railway
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "chat_history")
HISTORY_FILE = os.path.join(HISTORY_DIR, "chat.log")
MAX_HISTORY_LINES = 1000

# Создаём папку
try:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    print(f"✅ Папка создана: {HISTORY_DIR}")
except Exception as e:
    print(f"❌ Ошибка создания папки: {e}")

# Функция принудительной записи
def write_to_log(content: str):
    """Принудительная запись в файл с синхронизацией"""
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(content)
            f.flush()  # Принудительный сброс буфера
            os.fsync(f.fileno())  # Принудительная запись на диск
        return True
    except Exception as e:
        print(f"❌ Ошибка записи: {e}")
        return False

# Создаём заголовок если файл пустой
if not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0:
    header = f"# История чата LostEarth\n# Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    write_to_log(header)
    print(f"✅ Файл создан: {HISTORY_FILE}")

def add_to_chat_memory(username: str, message: str, is_bot: bool = False):
    """Добавляет сообщение в файл истории чата с принудительной записью"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🤖 Эндерия" if is_bot else f"👤 {username}"
        line = f"[{timestamp}] {prefix}: {message}\n"
        
        # Записываем
        if write_to_log(line):
            print(f"💾 УСПЕШНО! Записано в {HISTORY_FILE}: [{timestamp}] {prefix}: {message[:30]}...")
        else:
            print(f"❌ НЕ УДАЛОСЬ записать в файл")
            
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def get_chat_history(limit: int = 50) -> str:
    """Возвращает последние N сообщений из истории чата"""
    try:
        if not os.path.exists(HISTORY_FILE):
            print(f"⚠️ Файл {HISTORY_FILE} не существует")
            return ""
        
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        print(f"📖 Читаю историю чата, всего строк в файле: {len(lines)}")
        
        # Пропускаем заголовки
        messages = [l.strip() for l in lines if not l.startswith("#") and l.strip()]
        
        if not messages:
            return ""
        
        # Берём последние limit сообщений
        last_messages = messages[-limit:] if len(messages) > limit else messages
        return "\n".join(last_messages)
        
    except Exception as e:
        print(f"❌ Ошибка чтения: {e}")
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

ВАЖНО: Прочитай всю историю чата выше. Отвечай естественно, как участник чата.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_last_question = {}
user_greeted = {}
user_last_time = {}

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username]))

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик"]
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
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 250,
                    "temperature": 0.85,
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip(), True
                return "", False
    except:
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False) -> str:
    global current_online, current_max
    
    # Сохраняем вопрос пользователя в лог
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
    
    # Если уже здоровались и снова привет
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"💜 {username}, мы уже общаемся! Что хотел узнать?"
        add_to_memory(username, user_message, response)
        add_to_chat_memory(username, response, is_bot=True)
        return response
    
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = "НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    
    full_prompt = f"""{greeting_instruction}

{user_ctx}

{chat_ctx}

{username} написал: {user_message}
Это ответ на сообщение бота: {"ДА" if is_reply else "НЕТ"}

Ответь как Эндерия (2-4 предложения). Будь милой и дружелюбной. В конце 1-2 эмодзи."""

    system_prompt = get_system_prompt(username, current_time, current_online, current_max)
    
    for model in MODELS_CHAIN:
        result, success = await ask_model(model, system_prompt, full_prompt)
        if success and result:
            result = re.sub(r'<[^>]+>', '', result)
            if not already_greeted:
                mark_greeted(username)
            add_to_memory(username, user_message, result)
            add_to_chat_memory(username, result, is_bot=True)
            return result
        await asyncio.sleep(0.3)
    
    fallback = f"💜 {username}, связь с Краем потеряна! Повтори позже 🐱"
    add_to_memory(username, user_message, fallback)
    add_to_chat_memory(username, fallback, is_bot=True)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
