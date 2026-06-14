import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
from io import BytesIO 
from dotenv import load_dotenv

from database import save_andy_dialog, save_chat_message

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen2.5-7b-instruct",
    "google/gemini-flash-1.5",
]

# ========== ПРЕМИУМ ЭМОДЗИ ==========
ENDERIA_EMOJI = {
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "cat_up": "5269698007724499331",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "heart": "5199427253225667842",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "magic": "5474144592817318927",
    "joystick": "5870717606364713020",
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CAT_DANCE = emoji(ENDERIA_EMOJI["cat_dance"], "🐱")
E_CAT_OK = emoji(ENDERIA_EMOJI["cat_ok"], "👍")
E_CAT_UP = emoji(ENDERIA_EMOJI["cat_up"], "👍")
E_CAT_SURPRISED = emoji(ENDERIA_EMOJI["cat_surprised"], "😲")
E_RABBIT = emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")
E_ANIME = emoji(ENDERIA_EMOJI["anime_dance"], "💃")
E_HEART = emoji(ENDERIA_EMOJI["heart"], "💜")
E_CROWN = emoji(ENDERIA_EMOJI["crown"], "👑")
E_HOUSE = emoji(ENDERIA_EMOJI["house"], "🏠")
E_NOTE = emoji(ENDERIA_EMOJI["note"], "📝")
E_MAGIC = emoji(ENDERIA_EMOJI["magic"], "✨")
E_JOYSTICK = emoji(ENDERIA_EMOJI["joystick"], "🎮")

# ========== ПАМЯТЬ ==========
user_memory = defaultdict(lambda: deque(maxlen=90))
user_last_greet = {}  
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username])[-90:])

def can_greet(username: str) -> bool:
    if username not in user_last_greet:
        return True
    last = user_last_greet[username]
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    return datetime.now() - last > timedelta(hours=2)

def mark_greeted(username: str):
    user_last_greet[username] = datetime.now().isoformat()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "ку", "доброе"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names or clean_text == "энд"

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["энди", "енди", "энд"]
    return any(keyword in text_lower for keyword in keywords)

# ========== ОНЛАЙН ==========
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "бот" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ КАЖДЫЕ 3 ЧАСА ==========
spontaneous_enabled = True
spontaneous_messages_list = [] # Заглушка для импорта

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        # Спим ровно 10800 секунд (3 часа)
        await asyncio.sleep(10800)
        
        if spontaneous_enabled and OPENROUTER_API_KEY:
            system_prompt = (
                "ты энди, девушка-эндермен. придумай одно короткое случайное сообщение "
                "(1-2 предложения) для майнкрафт чата, чтобы начать разговор. "
                "пиши с маленькой буквы, без приветствий и используй разговорный стиль."
            )
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": MODELS_CHAIN[0],
                            "messages": [{"role": "system", "content": system_prompt}],
                            "max_tokens": 150,
                            "temperature": 0.9,
                        },
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = data["choices"][0]["message"]["content"].strip()
                            result = re.sub(r'<[^>]+>', '', result)
                            await bot.send_message(chat_id, f"{E_CAT_DANCE} {result} {E_HEART}", parse_mode="HTML")
            except Exception as e:
                print(f"ошибка генерации спонтанного сообщения: {e}")

# ========== ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ (ТОЛЬКО ДЛЯ АДМИНА) ==========

# Лучшие модели для генерации изображений через OpenRouter
IMAGE_MODELS = {
    "flux": "flux/flux-1-pro",           # Самая качественная
    "midjourney": "flux/midjourney"       # Стиль Midjourney
}

# Счётчик генераций для админа
admin_gen_counter = 0
admin_last_gen_reset = datetime.now()

async def generate_image_flux(prompt: str) -> BytesIO | None:
    """
    Генерация через Flux Pro - самая качественная модель
    Использует OpenRouter API
    """
    global admin_gen_counter
    
    if not OPENROUTER_API_KEY:
        print("❌ Нет OPENROUTER_API_KEY для генерации")
        return None
    
    # Расширяем промпт для лучшего качества
    enhanced_prompt = f"""{prompt}
    
Style: cinematic, ultra high quality, 8K, photorealistic, detailed, professional
Negative prompt: blurry, low quality, distorted, ugly"""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": IMAGE_MODELS["flux"],
        "prompt": enhanced_prompt,
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "guidance": 7.5,
        "n": 1,
        "response_format": "url"
    }
    
    try:
        print(f"🎨 Генерация Flux: {prompt[:50]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Извлекаем URL изображения
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0].get("message", {}).get("content", "")
                        
                        # Ищем URL изображения в ответе
                        import re
                        url_pattern = r'https?://[^\s]+\.(?:png|jpg|jpeg|webp|gif)'
                        urls = re.findall(url_pattern, content)
                        
                        if urls:
                            image_url = urls[0]
                            print(f"✅ URL получен: {image_url[:100]}...")
                            
                            # Скачиваем изображение
                            async with session.get(image_url) as img_resp:
                                if img_resp.status == 200:
                                    admin_gen_counter += 1
                                    return BytesIO(await img_resp.read())
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка Flux: {response.status} - {error_text[:200]}")
                    return None
                    
    except Exception as e:
        print(f"❌ Ошибка генерации Flux: {e}")
        return None
    
    return None

async def generate_image_midjourney(prompt: str) -> BytesIO | None:
    """
    Генерация через Midjourney стиль
    Использует OpenRouter API
    """
    global admin_gen_counter
    
    if not OPENROUTER_API_KEY:
        print("❌ Нет OPENROUTER_API_KEY для генерации")
        return None
    
    # Промпт в стиле Midjourney
    enhanced_prompt = f"""{prompt}
--ar 1:1 --style raw --v 6 --stylize 250 --quality 2

Style: cinematic, hyperdetailed, 8K, masterpiece, professional photography
Lighting: soft natural lighting, volumetric light
Colors: vibrant, rich"""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": IMAGE_MODELS["midjourney"],
        "prompt": enhanced_prompt,
        "width": 1024,
        "height": 1024,
        "steps": 25,
        "guidance": 7,
        "n": 1,
        "response_format": "url"
    }
    
    try:
        print(f"🎨 Генерация Midjourney: {prompt[:50]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0].get("message", {}).get("content", "")
                        
                        import re
                        url_pattern = r'https?://[^\s]+\.(?:png|jpg|jpeg|webp|gif)'
                        urls = re.findall(url_pattern, content)
                        
                        if urls:
                            image_url = urls[0]
                            print(f"✅ URL получен: {image_url[:100]}...")
                            
                            async with session.get(image_url) as img_resp:
                                if img_resp.status == 200:
                                    admin_gen_counter += 1
                                    return BytesIO(await img_resp.read())
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка Midjourney: {response.status} - {error_text[:200]}")
                    return None
                    
    except Exception as e:
        print(f"❌ Ошибка генерации Midjourney: {e}")
        return None
    
    return None

async def generate_image_fallback_free(prompt: str) -> BytesIO | None:
    """
    Бесплатный fallback через Pollinations (без ключа, высокое качество)
    Используется если OpenRouter не работает
    """
    import urllib.parse
    
    # Улучшенный промпт для лучшего качества
    enhanced_prompt = urllib.parse.quote(
        f"{prompt}, masterpiece, ultra high quality, photorealistic, 4K, detailed, cinematic lighting"
    )
    
    # Используем улучшенные параметры
    url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}?width=1024&height=1024&nologo=true"
    
    try:
        print(f"🎨 Fallback генерация: {prompt[:50]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    print("✅ Fallback успешен")
                    return BytesIO(await resp.read())
    except Exception as e:
        print(f"❌ Ошибка fallback: {e}")
    
    return None

async def generate_best_image(prompt: str, use_midjourney: bool = False) -> BytesIO | None:
    """
    Главная функция генерации - использует лучшую доступную модель
    Сначала пробует Flux Pro, потом Midjourney, потом бесплатный fallback
    """
    # Сначала пробуем Flux Pro (самое качественное)
    result = await generate_image_flux(prompt)
    if result:
        return result
    
    # Если Flux не сработал, пробуем Midjourney
    if use_midjourney:
        result = await generate_image_midjourney(prompt)
        if result:
            return result
    
    # В последнюю очередь - бесплатный fallback
    result = await generate_image_fallback_free(prompt)
    if result:
        return result
    
    return None

def get_gen_stats() -> dict:
    """Возвращает статистику генераций для админа"""
    global admin_gen_counter, admin_last_gen_reset
    
    # Проверяем, не пора ли сбросить счётчик (раз в месяц)
    now = datetime.now()
    if (now - admin_last_gen_reset).days >= 30:
        admin_gen_counter = 0
        admin_last_gen_reset = now
    
    return {
        "total_generations": admin_gen_counter,
        "last_reset": admin_last_gen_reset.strftime("%Y-%m-%d"),
        "models": list(IMAGE_MODELS.keys())
    }

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    await save_chat_message(username, user_message, is_bot=False)
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    can_say_greet = can_greet(username)
    context = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if is_greeting_msg and can_say_greet and not is_reply:
        mark_greeted(username)
        response = f"{E_CAT_DANCE} привет, {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if is_greeting_msg and not can_say_greet and not is_reply:
        response = f"{E_CAT_DANCE} {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    if OPENROUTER_API_KEY:
        try:
            system_prompt = f"""ты энди, девушка-эндермен

история диалога с {username}:
{context}

СТРОГИЕ ПРАВИЛА (НАРУШАТЬ НЕЛЬЗЯ):
1. ЗАПРЕЩЕНО писать "рад слышать", "рада слышать", "рад это слышать"
2. ЗАПРЕЩЕНО писать "всегда рада помочь", "рада помочь"
3. НЕ подписывай сообщения как "энди"
4. НЕ пиши "привет" если уже общались (смотри историю)
5. Отвечай коротко и по делу, 1-3 предложения
6. Используй разговорный стиль, как в переписке с другом
7. Пиши с маленькой буквы
8. Ставь эмодзи {E_CAT_DANCE} {E_HEART} {E_MAGIC} в конце или начале
9. НЕ используй шаблонные фразы

информация (отвечай только если спросили):
- сервер lostearth, ip java: 150.241.85.40:25565, bedrock: 150.241.85.40:19132
- режимы: мирный (заявка через бота) и smp (без заявки)
- онлайн сейчас: {current_online}/{current_max}
- тгк: @LostEarthSMP

игры: энди кубик, энди футбол, энди плюнуть, энди фарма

текущее сообщение: {user_message}

ответь по-человечески, без шаблонов:"""
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": model,
                                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                                "max_tokens": 500,
                                "temperature": 0.9,
                            },
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                except Exception as e:
                    print(f"модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"ошибка ии: {e}")
    
    fallbacks = [
        f"{E_CAT_DANCE} {username} {E_HEART}",
        f"{E_CAT_OK} {username} {E_HEART}",
        f"{E_MAGIC} {username} {E_CAT_DANCE}",
        f"{E_CAT_UP} {username} {E_HEART}",
    ]
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
