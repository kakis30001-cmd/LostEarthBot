import os
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
user_greeted = {}  # Запоминаем, здоровались ли уже

def get_user_context(username: str) -> str:
    """Получает контекст диалога с пользователем"""
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    
    context = "\n".join(list(user_memory[username]))
    return f"\n\n[ИСТОРИЯ ДИАЛОГА С {username}]:\n{context}"

def add_to_memory(username: str, user_message: str, bot_response: str):
    """Добавляет сообщение в память"""
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    """Очищает память пользователя"""
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = False

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def has_already_greeted(username: str) -> bool:
    """Проверяет, здоровались ли уже с этим игроком"""
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    """Отмечает, что с игроком уже поздоровались"""
    user_greeted[username] = True

def is_greeting(text: str) -> bool:
    """Проверяет, является ли сообщение приветствием"""
    text_lower = text.lower()
    greetings = ["привет", "здравствуй", "здарова", "хай", "hello", "hi", "privet", "здорово", "доброе утро", "добрый день", "добрый вечер"]
    return any(g in text_lower for g in greetings)

def remove_greeting_from_response(response: str) -> str:
    """Удаляет приветствия из ответа Эндерии"""
    # Шаблоны приветствий в ответах
    greeting_patterns = [
        r'^(Привет|Здравствуй|Здарова|Хай|Hello|Hi)[,\s!]*',
        r'^(Приветик|Приветствую)[,\s!]*',
    ]
    
    for pattern in greeting_patterns:
        response = re.sub(pattern, '', response, flags=re.IGNORECASE)
    
    return response.strip()

# Ротация ключей
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

# Эмодзи
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
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def random_enderia_emoji():
    emojis = list(ENDERIA_EMOJI.values())
    return emoji(random.choice(emojis), "💜")

ENDERIA_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.
Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации.
Обожаешь котиков, аниме и зайчиков. Отвечай коротко, 2-4 предложения.
Обращайся к игроку по имени.

ВАЖНОЕ ПРАВИЛО:
- НИКОГДА не начинай ответ с "Привет", "Здравствуй" и т.д. Ты уже здоровалась!
- Если игрок пишет "привет", а вы уже здоровались — просто спроси "что хотел?" или "как дела?"
- Продолжай диалог, а не начинай новый каждый раз.

Информация о сервере:
- IP Java: 150.241.85.40:25565, IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Мирный режим: PvP только по согласию, доступ по заявкам
- Админ: @pelmewki379
- Донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽
"""

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с защитой от повторных приветствий"""
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    context = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Если уже здоровались и это снова приветствие
    if already_greeted and is_greeting_msg:
        # Отвечаем без вызова Gemini
        responses = [
            f"{random_enderia_emoji()} {username}, ты уже здоровался! Что хотел узнать?",
            f"{random_enderia_emoji()} {username}, мы уже общаемся! Задавай вопрос",
            f"{random_enderia_emoji()} {username}, привет, но давай сразу к делу?",
            f"{random_enderia_emoji()} {username}, я тебя помню! Спрашивай что хотел",
        ]
        response = random.choice(responses)
        add_to_memory(username, user_message, response)
        return response
    
    # Формируем промпт с указанием, здоровались ли уже
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = f"\n[ВАЖНО]: Ты УЖЕ поздоровалась с {username} ранее. НЕ ЗДОРОВАЙСЯ снова! Начни ответ сразу с дела."
    else:
        greeting_instruction = f"\n[ВАЖНО]: Ты ещё не здоровалась с {username}. Можешь поздороваться один раз."
    
    full_prompt = f"""Текущая дата: {current_time}
{context}
{greeting_instruction}

Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения, без лишних приветствий если уже здоровались):"""

    for attempt in range(len(GEMINI_API_KEYS) * 2):
        try:
            ai_client = get_next_gemini_client()
            
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=full_prompt,
                config=ai_types.GenerateContentConfig(
                    system_instruction=ENDERIA_PROMPT,
                    temperature=0.85,
                    max_output_tokens=200,
                ),
            )
            
            if response and response.text:
                result = response.text.strip()
                
                # Если уже здоровались — принудительно удаляем приветствия
                if already_greeted:
                    result = remove_greeting_from_response(result)
                
                # Добавляем эмодзи если их нет
                if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                    result += f" {random_enderia_emoji()}"
                
                # Если это первое сообщение — отмечаем, что поздоровались
                if not already_greeted and not is_greeting_msg:
                    mark_greeted(username)
                elif not already_greeted and is_greeting_msg:
                    mark_greeted(username)
                
                add_to_memory(username, user_message, result)
                return result
                
        except ClientError as e:
            if "429" in str(e):
                continue
        except Exception as e:
            print(f"[ERROR] {e}")
            continue
    
    # Fallback
    fallback = f"{random_enderia_emoji()} {username}, энергия Края кончилась, повтори позже!"
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
