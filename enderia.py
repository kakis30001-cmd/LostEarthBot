import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

# ========== OPENROUTER НАСТРОЙКИ ==========
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ТОП-5 ЛУЧШИХ БЕСПЛАТНЫХ МОДЕЛЕЙ (отсортированы по качеству)
MODELS_CHAIN = [
    "openai/gpt-oss-120b",                    # OpenAI, очень умная, отличный русский
    "nousresearch/hermes-3-405b-instruct",    # 405B, огромная, умная
    "meta-llama/llama-3.3-70b-instruct",      # 70B, стабильная, хорошая
    "qwen/qwen3-coder-480b-a35b-instruct",    # 480B, огромный контекст
    "nvidia/nemotron-nano-12b-v2",            # 12B, быстрая, хорошая
]

# Запасные быстрые модели (если топовые упадут)
FALLBACK_MODELS = [
    "meta-llama/llama-3.2-3b-instruct",       # 3B, очень быстрая
    "liquid/lfm2.5-1.2b-instruct",            # 1.2B, супер быстрая для запаса
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
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def random_enderia_emoji():
    emojis = list(ENDERIA_EMOJI.values())
    return emoji(random.choice(emojis), "")

def get_enderia_emojis():
    count = random.choices([1, 2], weights=[70, 30])[0]
    emojis = []
    for _ in range(count):
        emojis.append(random_enderia_emoji())
    return " ".join(emojis)

# ========== СИСТЕМНЫЙ ПРОМПТ ==========
def get_system_prompt(username: str, current_time: str) -> str:
    return f"""Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

Твой образ: высокая эндермен-девушка с фиолетовыми волосами и светящимися глазами. Ты паришь и телепортируешься.

Твой характер: добрая, загадочная. Обожаешь котиков, аниме и зайчиков.

Стиль общения: говори ласково, используй обращения "игрок~", "дружок~". Отвечай коротко, 2-4 предложения.

ИНФОРМАЦИЯ О СЕРВЕРЕ LostEarth:

Версия: 1.21 — 1.26+
Админ: @pelmewki379

РЕЖИМЫ ИГРЫ (ОБЯЗАТЕЛЬНО ЗНАЙ ОБА):

1. МИРНЫЙ РЕЖИМ (PvE):
   - PvP только по согласию
   - Защита от гриферства
   - Нельзя ломать чужие постройки
   - Доступ по ЗАЯВКАМ (@pelmewki379)

2. SMP РЕЖИМ (PvP):
   - PvP везде (кроме спавна)
   - Можно воровать и рейдить
   - Запрещены читы и X-Ray

IP-АДРЕСА:
- JAVA: 150.241.85.40:25565
- BEDROCK: 150.241.85.40:19132

ДОНАТЫ (у @pelmewki379):
Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽

ПРАВИЛА:
- Запрещены читы, X-Ray → БАН
- Запрещена реклама → БАН
- Оскорбление админа → МУТ

Игрок: {username}
Текущая дата: {current_time}

Важно: НЕ используй HTML теги в ответе! Только текст и обычные эмодзи. Эмодзи ставь в конце ответа."""

# ========== ЗАПРОС К КОНКРЕТНОЙ МОДЕЛИ ==========
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
                    "max_tokens": 200,
                    "temperature": 0.85,
                    "top_p": 0.95,
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=25)
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
        print(f"⚠️ Модель {model} исключение: {e}")
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ С ЦЕПОЧКОЙ МОДЕЛЕЙ ==========
async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с автоматическим переключением моделей"""
    
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
        response = f"{get_enderia_emojis()} {username}, ты уже здоровался! Что хотел узнать про LostEarth?"
        add_to_memory(username, user_message, response)
        return response
    
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = "Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    
    full_prompt = f"""{greeting_instruction}
{context}

Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). В конце ответа поставь эмодзи (🐱💜🐰). Не используй HTML теги!"""

    system_prompt = get_system_prompt(username, current_time)
    
    # Пробуем топовые модели
    all_models = MODELS_CHAIN + FALLBACK_MODELS
    
    for model_index, model in enumerate(all_models):
        print(f"🔄 [{model_index + 1}/{len(all_models)}] Модель: {model}")
        
        result, success = await ask_model(model, system_prompt, full_prompt)
        
        if success and result and len(result) > 10:
            print(f"✅ УСПЕХ! Модель {model} ответила!")
            
            # Убираем все HTML теги из ответа ИИ
            result = re.sub(r'<[^>]+>', '', result)
            
            # Добавляем эмодзи если их нет
            if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                result += f" {get_enderia_emojis()}"
            
            # Отмечаем что поздоровались
            if not already_greeted:
                mark_greeted(username)
            
            add_to_memory(username, user_message, result)
            return result
        
        # Небольшая задержка перед следующей моделью
        await asyncio.sleep(0.3)
    
    # Если все модели отказали
    print("❌ КРИТИЧНО: Все модели не ответили!")
    fallbacks = [
        f"{get_enderia_emojis()} {username}, связь с Краем потеряна! Повтори позже 💜",
        f"{get_enderia_emojis()} {username}, на LostEarth есть два режима: Мирный (PvP по согласию) и SMP (можно рейдить)! 🐱",
        f"{get_enderia_emojis()} {username}, IP Java: 150.241.85.40:25565, Bedrock: 19132. Заходи играть! 🐰",
        f"{get_enderia_emojis()} {username}, донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽ 💜",
        f"{get_enderia_emojis()} {username}, админ: @pelmewki379, пиши по любым вопросам! 🐱",
    ]
    fallback = random.choice(fallbacks)
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
