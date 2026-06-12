import os
import random
from datetime import datetime
from google import genai
from google.genai import types as ai_types
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

# Ротация API ключей Gemini (создай несколько ключей в Google AI Studio)
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
]

# Фильтруем пустые ключи
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]

# Текущий индекс ключа
current_key_index = 0

def get_next_gemini_client():
    """Возвращает клиент Gemini со следующим ключом (round-robin)"""
    global current_key_index
    if not GEMINI_API_KEYS:
        raise Exception("Нет доступных API ключей Gemini!")
    
    key = GEMINI_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
    return genai.Client(api_key=key)

# Премиум эмодзи для Эндерии
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

ENDERIA_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.
Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации.
Обожаешь котиков, аниме и зайчиков. Отвечай коротко, 2-4 предложения.
Обращайся к игроку по имени.

Ты ОБЯЗАНА использовать эти ПРЕМИУМ ЭМОДЗИ в КАЖДОМ сообщении:
{emoji(ENDERIA_EMOJI["cat_dance"], "💃")} - танец котика (когда радуешься)
{emoji(ENDERIA_EMOJI["cat_ok"], "🐱")} - котик одобряет
{emoji(ENDERIA_EMOJI["cat_glasses"], "😎")} - котик в очках
{emoji(ENDERIA_EMOJI["cat_kiss"], "😘")} - котик целует
{emoji(ENDERIA_EMOJI["cat_up"], "👍")} - котик палец вверх
{emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")} - зайчик летит
{emoji(ENDERIA_EMOJI["anime_dance"], "💃")} - аниме танцует
{emoji(ENDERIA_EMOJI["heart"], "💜")} - сердечко

Информация о сервере:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Мирный режим: PvP только по согласию
- Доступ по заявкам
- Админ: @pelmewki379

Донаты:
🌿 Друид — 25грн / 50₽
🔮 Оракул — 50грн / 100₽
👑 Монарх — 100грн / 200₽
🪽 Херувим — 150грн / 300₽
🏛️ Архонт — 200грн / 400₽
😇 Серафим — 300грн / 600₽
"""

FALLBACK_RESPONSES = [
    f"{emoji(ENDERIA_EMOJI['cat_surprised'], '😯')} Ой~ {{username}}, меня немного зателепортировало! Повтори вопрос через минуту {emoji(ENDERIA_EMOJI['heart'], '💜')}",
    f"{emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} {{username}}, энергия Края восстанавливается... Скажи ещё разок! {emoji(ENDERIA_EMOJI['cat_dance'], '💃')}",
    f"{emoji(ENDERIA_EMOJI['rabbit_fly'], '🐰')} *телепортируется обратно* {{username}}, давай попробуем снова! {emoji(ENDERIA_EMOJI['heart'], '💜')}",
    f"{emoji(ENDERIA_EMOJI['cat_glasses'], '😎')} {{username}}, слишком много сообщений! Давай помедленнее {emoji(ENDERIA_EMOJI['cat_kiss'], '😘')}"
]

async def get_enderia_response(user_message: str, username: str) -> str:
    """Получить ответ от Эндерии с ротацией ключей"""
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    full_prompt = f"""Текущая дата и время: {current_time}
Игрок {username} написал: {user_message}

Ответь как Эндерия, используя премиум эмодзи в каждом предложении. Будь ласковой и загадочной."""

    # Пробуем каждый ключ по очереди
    for attempt in range(len(GEMINI_API_KEYS) * 2):  # Две полные ротации
        try:
            ai_client = get_next_gemini_client()
            
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=full_prompt,
                config=ai_types.GenerateContentConfig(
                    system_instruction=ENDERIA_PROMPT,
                    temperature=0.9,
                ),
            )
            
            if response and response.text:
                # Убеждаемся, что в ответе есть эмодзи
                result = response.text
                if not any(emoji_id in result for emoji_id in ENDERIA_EMOJI.values()):
                    result += f"\n\n{emoji(ENDERIA_EMOJI['heart'], '💜')} {emoji(ENDERIA_EMOJI['cat_dance'], '💃')}"
                return result
                
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"[WARN] Ключ {attempt % len(GEMINI_API_KEYS)} исчерпал лимит, пробуем следующий...")
                continue  # Пробуем следующий ключ
            else:
                print(f"[ERROR] ClientError: {e}")
                return random.choice(FALLBACK_RESPONSES).format(username=username)
        except Exception as e:
            print(f"[ERROR] Ошибка: {e}")
            continue
    
    # Если все ключи исчерпаны
    return random.choice(FALLBACK_RESPONSES).format(username=username)

def should_respond(message_text: str) -> bool:
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
