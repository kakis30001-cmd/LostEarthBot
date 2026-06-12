import os
import random
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

# Ротация API ключей Gemini
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]

# Фильтруем пустые ключи
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]
current_key_index = 0

def get_next_gemini_client():
    global current_key_index
    if not GEMINI_API_KEYS:
        raise Exception("Нет доступных API ключей Gemini!")
    key = GEMINI_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
    return genai.Client(api_key=key)

# ВСЕ ПРЕМИУМ ЭМОДЗИ ДЛЯ ЭНДЕРИИ
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
    """Случайное премиум эмодзи"""
    emojis = list(ENDERIA_EMOJI.values())
    return emoji(random.choice(emojis), "💜")

def get_enderia_emojis():
    """Возвращает 1-2 случайных эмодзи (иногда 3, но редко)"""
    count = random.choices([1, 2, 3], weights=[50, 40, 10])[0]  # 50% - 1, 40% - 2, 10% - 3
    emojis = []
    for _ in range(count):
        emojis.append(random_enderia_emoji())
    return " ".join(emojis)

ENDERIA_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.
Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации.
Обожаешь котиков, аниме и зайчиков. Отвечай коротко, 2-4 предложения.
Обращайся к игроку по имени.

Важно: НЕ ставь много эмодзи подряд! Используй 1-2 эмодзи на ответ, максимум 3.
Эмодзи должны быть в конце ответа или после обращения к игроку.

Доступные эмодзи (используй их):
{emoji(ENDERIA_EMOJI['cat_dance'], '💃')} - танец котика
{emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} - котик одобряет
{emoji(ENDERIA_EMOJI['cat_glasses'], '😎')} - котик в очках
{emoji(ENDERIA_EMOJI['cat_kiss'], '😘')} - котик целует
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
    f"Ой~ {{username}}, меня немного зателепортировало! Повтори вопрос через минутку {emoji(ENDERIA_EMOJI['cat_surprised'], '😯')}",
    f"{{username}}, энергия Края восстанавливается... Скажи ещё разок! {emoji(ENDERIA_EMOJI['cat_ok'], '🐱')}",
    f"*телепортируется* {{username}}, давай попробуем снова! {emoji(ENDERIA_EMOJI['heart'], '💜')}",
    f"{{username}}, слишком много запросов! Подожди немного {emoji(ENDERIA_EMOJI['cat_glasses'], '😎')}",
]

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с ротацией ключей"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    full_prompt = f"""Текущая дата и время: {current_time}
Игрок {username} написал: {user_message}

Ответь как Эндерия. Используй 1-2 эмодзи в конце ответа, максимум 3. Не ставь много эмодзи подряд!"""

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
                # Проверяем, есть ли уже эмодзи в ответе
                has_emoji = any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values())
                
                # Добавляем 1-2 эмодзи если их нет
                if not has_emoji:
                    result += f" {get_enderia_emojis()}"
                # Если эмодзи слишком много (больше 3), заменяем на 1-2
                elif result.count('<tg-emoji') > 3:
                    # Убираем все эмодзи и добавляем 1-2 новых
                    import re
                    result = re.sub(r'<tg-emoji[^>]+>[^<]*</tg-emoji>', '', result).strip()
                    result += f" {get_enderia_emojis()}"
                
                return result
                
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"[WARN] Ключ {attempt} исчерпал лимит, пробуем следующий...")
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
