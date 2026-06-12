import os
import random
from datetime import datetime
from collections import defaultdict, deque
from google import genai
from google.genai import types as ai_types
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
# Храним последние 5 сообщений для каждого пользователя
user_memory = defaultdict(lambda: deque(maxlen=5))

def get_user_context(username: str) -> str:
    """Получает контекст диалога с пользователем"""
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    
    context = "\n".join(list(user_memory[username]))
    return f"\n\nИстория диалога с {username}:\n{context}\n\nУчитывай эту историю, чтобы отвечать последовательно. Не повторяй приветствия, если уже поздоровались!"

def add_to_memory(username: str, user_message: str, bot_response: str):
    """Добавляет сообщение в память"""
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    """Очищает память пользователя (если нужно)"""
    if username in user_memory:
        user_memory[username].clear()

# Ротация API ключей Gemini
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

# ПРЕМИУМ ЭМОДЗИ
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

ENDERIA_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.
Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации.
Обожаешь котиков, аниме и зайчиков. Отвечай коротко, 2-4 предложения.
Обращайся к игроку по имени.

ВАЖНО:
1. Запоминай, что ты уже общалась с игроком. Если он уже поздоровался — не здоровайся снова!
2. Продолжай диалог логично, учитывай предыдущие сообщения.
3. Не повторяй одну и ту же информацию дважды.
4. Если игрок задал вопрос, а потом уточняет — отвечай как в реальном разговоре.

Используй 1-2 эмодзи в конце ответа, максимум 3.

Доступные эмодзи:
{emoji(ENDERIA_EMOJI['cat_dance'], '💃')} - танец котика
{emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} - котик одобряет
{emoji(ENDERIA_EMOJI['rabbit_fly'], '🐰')} - зайчик летит
{emoji(ENDERIA_EMOJI['heart'], '💜')} - сердечко

Информация о сервере LostEarth:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Мирный режим: PvP только по согласию, доступ по заявкам
- Админ: @pelmewki379

Донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽
"""

FALLBACK_RESPONSES = [
    "Ой~ {username}, меня немного зателепортировало! Повтори вопрос через минутку 💜",
    "{username}, энергия Края восстанавливается... Скажи ещё разок! 🐱",
    "*телепортируется* {username}, давай попробуем снова! 💜",
]

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с учётом истории диалога"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Получаем контекст диалога
    context = get_user_context(username)
    
    full_prompt = f"""Текущая дата и время: {current_time}
{context}

Сейчас {username} написал: {user_message}

Ответь как Эндерия. Если вы уже общались — НЕ ЗДОРОВАЙСЯ заново, просто продолжай разговор!"""

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
                
                # Добавляем эмодзи если их нет
                if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                    result += f" {random_enderia_emoji()}"
                
                # Сохраняем в память
                add_to_memory(username, user_message, result)
                
                return result
                
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"[WARN] Ключ {attempt} исчерпал лимит")
                continue
            else:
                print(f"[ERROR] ClientError: {e}")
                return random.choice(FALLBACK_RESPONSES).format(username=username)
        except Exception as e:
            print(f"[ERROR] Ошибка: {e}")
            continue
    
    return random.choice(FALLBACK_RESPONSES).format(username=username)

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
