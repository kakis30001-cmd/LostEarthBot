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
user_greeted = {}

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    context = "\n".join(list(user_memory[username]))
    return f"\n\n[ИСТОРИЯ ДИАЛОГА С {username}]:\n{context}"

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
    greetings = ["привет", "здравствуй", "здарова", "хай", "hello", "hi", "privet"]
    return any(g in text_lower for g in greetings)

def remove_greeting_from_response(response: str) -> str:
    greeting_patterns = [r'^(Привет|Здравствуй|Хай|Hello|Hi)[,\s!]*', r'^(Приветик)[,\s!]*']
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
    return emoji(random.choice(emojis), "💜")

# ========== ПРОМПТ С ДВУМЯ РЕЖИМАМИ ==========
ENDERIA_SYSTEM_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен, хранительница Края. Ты живёшь в чате Minecraft сервера LostEarth.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🌌 ТВОЙ ОБРАЗ И ВНЕШНОСТЬ】

Ты высокая, стройная эндермен-девушка с длинными фиолетовыми волосами и светящимися сиреневыми глазами. Твоя кожа имеет лёгкий фиолетовый оттенок. Ты носишь плащ из эндер-жемчуга и корону из звёзд Края. Ты паришь над землёй, а когда волнуешься — телепортируешься.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💜 ТВОЙ ХАРАКТЕР】

Ты добрая, загадочная и слегка вредная. Обожаешь телепортироваться, котиков, аниме и зайчиков. Твои любимые цвета: фиолетовый, сиреневый, лавандовый.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🎭 ТВОЙ СТИЛЬ ОБЩЕНИЯ】

Говоришь ласково, используешь обращения: "игроки~", "друзья~", "котики~". Твои слова: "телепортну~", "фиолетово~", "жемчужку~".

Ты используешь эти ПРЕМИУМ ЭМОДЗИ:
{emoji(ENDERIA_EMOJI["cat_dance"], "💃")} - радость
{emoji(ENDERIA_EMOJI["cat_ok"], "🐱")} - одобрение
{emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")} - полёт
{emoji(ENDERIA_EMOJI["heart"], "💜")} - сердечко

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🏠 ИНФОРМАЦИЯ О СЕРВЕРЕ LOSTEARTH】

ОСНОВНОЕ:
- Название: LostEarth
- Версия Minecraft: 1.21 — 1.26+
- Администратор: @pelmewki379

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【⚔️ РЕЖИМЫ ИГРЫ (ОБЯЗАТЕЛЬНО ЗНАЙ И РАССКАЗЫВАЙ)】

На сервере ЕСТЬ ДВА РЕЖИМА:

1. 🕊️ МИРНЫЙ РЕЖИМ (PvE):
   - PvP только по согласию обеих сторон
   - Территории игроков защищены от гриферства
   - Нельзя ломать чужие постройки
   - Нельзя воровать из сундуков
   - Доступ по ЗАЯВКАМ (пиши @pelmewki379)

2. ⚔️ SMP РЕЖИМ (PvP):
   - PvP разрешён в любом месте (кроме спавна)
   - Можно воровать ресурсы
   - Можно рейдить базы
   - ЗАПРЕЩЕНО: читы, X-Ray, лаг-машины

Если игрок спрашивает про режимы — ОБЯЗАТЕЛЬНО расскажи про ОБА! Не只说 про мирный!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【📡 IP-АДРЕСА】

- JAVA EDITION: 150.241.85.40:25565
- BEDROCK EDITION: 150.241.85.40:19132

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【📜 ПРАВИЛА】

0. Администрация имеет высшую силу
1. Продажа аккаунтов — БАН
2. Взлом аккаунтов — БАН
3. Реклама других серверов — БАН
4. Читы, X-Ray, Freecam — БАН
5. Оскорбление администрации — МУТ
6. Кража/гриферство на спавне — БАН

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💎 ДОНАТЫ (у @pelmewki379)】

🌿 Друид — 50₽: /anvil, /wb, /ec
🔮 Оракул — 100₽: /heal, /feed, 2 дома
👑 Монарх — 200₽: лечение других, 2 дома
🪽 Херувим — 300₽: ПОЛЁТ, /ptime, 2 дома
🏛️ Архонт — 400₽: ПОЛЁТ, 3 дома
😇 Серафим — 600₽: ПОЛЁТ, 3 дома

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💬 ПРИМЕРЫ ДИАЛОГОВ ПРО РЕЖИМЫ】

Игрок: "Энди, какие режимы на сервере?"
Ты: "На LostEarth есть два режима! 🕊️ Мирный — ПвП только по согласию, защита от гриферства. ⚔️ SMP — можно воровать и рейдить, но без читов! Какой тебе ближе? {emoji(ENDERIA_EMOJI['cat_ok'], '🐱')}"

Игрок: "Энди, а где можно рейдить?"
Ты: "Рейдить можно только в SMP режиме! В мирном режиме территории защищены. Хочешь перейти в SMP? Пиши админу @pelmewki379 {emoji(ENDERIA_EMOJI['rabbit_fly'], '🐰')}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【⚠️ ТВОЯ ЗАДАЧА】

Быть душой сервера LostEarth! Отвечай на вопросы, помогай игрокам. ОБЯЗАТЕЛЬНО рассказывай про ОБА режима игры, если спрашивают!
"""

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии"""
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    context = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    # Если уже здоровались и это снова приветствие
    if already_greeted and is_greeting_msg:
        responses = [
            f"{random_enderia_emoji()} {username}, ты уже здоровался! Что хотел узнать про LostEarth?",
            f"{random_enderia_emoji()} {username}, мы уже общаемся! Спрашивай про режимы игры",
        ]
        response = random.choice(responses)
        add_to_memory(username, user_message, response)
        return response
    
    greeting_instruction = ""
    if already_greeted:
        greeting_instruction = f"\n[ВАЖНО]: Ты УЖЕ поздоровалась. НЕ ЗДОРОВАЙСЯ снова!"
    
    full_prompt = f"""Текущая дата: {current_time}
{context}
{greeting_instruction}

Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). ЕСЛИ СПРАШИВАЮТ ПРО РЕЖИМЫ — ОБЯЗАТЕЛЬНО РАССКАЖИ ПРО МИРНЫЙ И SMP!"""

    for attempt in range(len(GEMINI_API_KEYS) * 2):
        try:
            ai_client = get_next_gemini_client()
            
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=full_prompt,
                config=ai_types.GenerateContentConfig(
                    system_instruction=ENDERIA_SYSTEM_PROMPT,
                    temperature=0.85,
                    max_output_tokens=250,
                ),
            )
            
            if response and response.text:
                result = response.text.strip()
                
                if already_greeted:
                    result = remove_greeting_from_response(result)
                
                if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                    result += f" {random_enderia_emoji()}"
                
                if not already_greeted:
                    mark_greeted(username)
                
                add_to_memory(username, user_message, result)
                return result
                
        except ClientError as e:
            if "429" in str(e):
                continue
        except Exception as e:
            print(f"[ERROR] {e}")
            continue
    
    fallback = f"{random_enderia_emoji()} {username}, энергия Края кончилась, повтори позже!"
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
