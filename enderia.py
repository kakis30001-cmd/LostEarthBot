import o
import random
import re
from datetime import datetime
from collections import defaultdict, deque
from google import genai
from google.genai import types as ai_types
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_last_question = {}
user_greeted = {}

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

# ========== РОТАЦИЯ КЛЮЧЕЙ GEMINI ==========
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]
current_key_index = 0

def get_next_gemini_client():
    global current_key_index
    if not GEMINI_API_KEYS:
        raise Exception("Нет доступных API ключей Gemini!")
    key = GEMINI_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
    return genai.Client(api_key=key)

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

# ========== ПРОМПТ ЭНДЕРИИ ==========
ENDERIA_SYSTEM_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

Твой образ: высокая эндермен-девушка с фиолетовыми волосами и светящимися глазами. Ты паришь и телепортируешься.

Твой характер: добрая, загадочная. Обожаешь котиков, аниме и зайчиков.

Стиль общения: говори ласково, используй обращения "игрок~", "дружок~".

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

Отвечай коротко, 2-4 предложения. Используй эмодзи только в конце ответа.
"""

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии"""
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    context = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Если уже здоровались и это снова приветствие
    if already_greeted and is_greeting_msg:
        response = f"{get_enderia_emojis()} {username}, ты уже здоровался! Что хотел узнать про LostEarth?"
        add_to_memory(username, user_message, response)
        return response
    
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = "Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ! Начни сразу с ответа."
    
    full_prompt = f"""Время: {current_time}
{context}
{greeting_instruction}

Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). В конце ответа поставь эмодзи. НЕ используй HTML теги!"""

    for attempt in range(len(GEMINI_API_KEYS) * 2):
        try:
            ai_client = get_next_gemini_client()
            
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=full_prompt,
                config=ai_types.GenerateContentConfig(
                    system_instruction=ENDERIA_SYSTEM_PROMPT,
                    temperature=0.85,
                    max_output_tokens=200,
                ),
            )
            
            if response and response.text:
                result = response.text.strip()
                
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
                
        except ClientError as e:
            if "429" in str(e):
                print(f"[WARN] Лимит ключа {attempt}")
                continue
        except Exception as e:
            print(f"[ERROR] {e}")
            continue
    
    fallback = f"{get_enderia_emojis()} {username}, энергия Края кончилась, повтори позже!"
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
