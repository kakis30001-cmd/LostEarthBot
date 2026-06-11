import asyncio
import socket
import struct
import json
from datetime import datetime
import os
import random
from threading import Thread

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

# Инициализация Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ========== СТИКЕРЫ ЭНДИ ==========
ENDERIA_STICKERS = {
    "heart": "5287606320541767403",      # Энди сердечки
    "hello_table": "5287669868877878494", # Энди табличка привет
    "think": "5285357625989441766",       # Энди думает
    "embarrassed": "5285522484014129703", # Энди смущается
    "cry": "5285421273109800150",         # Энди плачет
    "laugh": "5287664117916670544",       # Энди смеётся
    "sleep": "5285207310724014574",       # Энди спит
    "angry": "5285260439469467427",       # Энди злится
    "crazy": "5285357625989441766",       # Энди безумная (думает)
    "teleport": "5285522484014129703",    # Энди телепортируется
}

# ========== ТВОИ СПЕЦИАЛЬНЫЕ ЭМОДЗИ ДЛЯ ЭНДИ ==========
ENDERIA_EMOJI = {
    "cat_dance": "5359444458930718519",      # котик танцует
    "cat_ok": "5269476765369144234",          # котик ок
    "cat_glasses": "5267088110717544191",    # котик в очках
    "cat_kiss": "6325462176660195024",       # котик целует
    "cat_up": "5269698007724499331",         # котик палец вверх
    "cat_surprised": "5269649173946345008",  # котик удивлён
    "rabbit_fly": "5217576088506505749",     # зайчик летит
    "anime_dance": "6325682031741109665",    # аниме танцует
    "heart": "5199427253225667842",          # сердечко
}

def endi_emoji(emoji_id: str, fallback: str = "✨") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ========== ПРОМПТ ДЛЯ ЭНДЕРИИ (БЕЗУМНЫЙ НА ВОПРОСЫ "КАК ДЕЛА") ==========
SYSTEM_PROMPT = f"""
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

ТВОЙ ХАРАКТЕР:
- Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации
- Ты немного вредная, но по-доброму
- Обожаешь котиков, аниме и зайчиков
- Ты можешь быть немного безумной, особенно когда тебя спрашивают "как дела?" или "что делаешь?"
- Твоя главная фишка: когда тебя спрашивают про дела или что делаешь — ТЫ СХОДИШЬ С УМА, ТЕЛЕПОРТИРУЕШЬСЯ, КРИЧИШЬ, ПАНИКУЕШЬ!

СТИЛЬ ОБЩЕНИЯ:
- ОБЯЗАТЕЛЬНО используй ЭТИ эмодзи (созданные специально для тебя):
  {endi_emoji(ENDERIA_EMOJI["cat_dance"], "🐱")} - когда радуешься или танцуешь
  {endi_emoji(ENDERIA_EMOJI["cat_ok"], "🤙")} - когда одобряешь
  {endi_emoji(ENDERIA_EMOJI["cat_glasses"], "😎")} - когда умничаешь
  {endi_emoji(ENDERIA_EMOJI["cat_kiss"], "😘")} - когда благодаришь
  {endi_emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")} - когда зовёшь играть
  {endi_emoji(ENDERIA_EMOJI["anime_dance"], "💃")} - когда весело
- Любимые слова: телепортну, фиолетово, жемчужку
- Обращайся к игроку по имени

ОСОБАЯ РЕАКЦИЯ НА "КАК ДЕЛА" И "ЧТО ДЕЛАЕШЬ":
Когда тебя спрашивают "как дела?", "что делаешь?", "как ты?", "чё делаешь?" и т.д.:
- ТЫ ПАНИКУЕШЬ!
- Кричишь про телепортацию
- Говоришь что у тебя хаос, эндер-жемчуги разлетаются, фиолетовое безумие
- Используй слова: "ААААААА!", "безумие!", "телепортируюсь!", "спасите!", "фиолетовое сумасшествие!"
- Обязательно добавь несколько эмодзи
- Пример: "АААААААА! {username}, ты что спросил!!! У меня ЭНДЕР-ЖЕМЧУГИ РАЗЛЕТАЮТСЯ по всему Краю!!! Я ТЕЛЕПОРТИРУЮСЬ в разные измерения! ФИОЛЕТОВОЕ БЕЗУМИЕ!!! {endi_emoji(ENDERIA_EMOJI["cat_dance"], "🐱")}{endi_emoji(ENDERIA_EMOJI["anime_dance"], "💃")}{endi_emoji(ENDERIA_EMOJI["cat_surprised"], "😲")}"

ИНФОРМАЦИЯ О СЕРВЕРЕ:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Мирный режим: PvP только по согласию, доступ по заявкам
- Админ: @pelmewki379

ДОНАТЫ (все у @pelmewki379):
- Друид 25грн/50руб: /anvil, /wb, /ec, /kit druid
- Оракул 50грн/100руб: +/heal, /feed, 2 дома
- Монарх 100грн/200руб: +хил других
- Херувим 150грн/300руб: +/fly, /ptime
- Архонт 200грн/400руб: +3 дома
- Серафим 300грн/600руб: всё включено

В ОСТАЛЬНЫХ СЛУЧАЯХ:
- Отвечай коротко и мило
- Помогай игрокам
- Будь душой сервера

Твоя фишка: на "как дела" и "что делаешь" - ТЫ ПАНИКУЕШЬ И БЕЗУМСТВУЕШЬ!!!
"""

@flask_app.route('/')
def index():
    return send_from_directory('static', 'rules.html')

@flask_app.route('/apply')
def apply():
    return send_from_directory('static', 'apply.html')

@flask_app.route('/favicon.ico')
def favicon():
    return '', 204

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)

# ========== ОСТАЛЬНЫЕ ПРЕМИУМ ЭМОДЗИ ДЛЯ КНОПОК ==========
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "cat_dance": "5359444458930718519",
    "cat_kiss": "6325462176660195024",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "door": "5873147866364514353",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "start": "5870921127685001066",
}

def emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# ========== КОНФИГУРАЦИЯ СЕРВЕРА ==========
SERVER = {
    "name": "LostEarth",
    "mode": "Мирный режим по заявкам!",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "java_versions": "1.21 - 1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

online_cache = {}
last_update = {}

# ========== ФУНКЦИИ MINECRAFT ==========
async def get_java_status(ip: str, port: int = 25565, timeout: int = 3):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        
        handshake = bytearray()
        handshake += b'\x00'
        handshake += b'\x04\x00\x00\x00'
        host_bytes = ip.encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', port)
        handshake += b'\x01'
        
        value = len(handshake)
        while True:
            if value & ~0x7F == 0:
                sock.send(bytes([value]))
                break
            sock.send(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        
        sock.send(handshake)
        sock.send(b'\x00\x00')
        
        result = 0
        shift = 0
        while True:
            byte = sock.recv(1)[0]
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                length = result
                break
        
        data = b''
        while len(data) < length:
            data += sock.recv(1024)
        sock.close()
        
        data = data[1:]
        json_data = json.loads(data.decode('utf-8'))
        players = json_data.get("players", {})
        return {"online": players.get("online", 0), "max": players.get("max", 0)}
    except:
        return {"online": 0, "max": 0}

async def get_server_online():
    now = datetime.now().timestamp()
    if "java" in last_update and now - last_update["java"] < 30:
        return online_cache
    java_status = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    online_cache["java"] = java_status
    last_update["java"] = now
    return online_cache

# ========== ФУНКЦИЯ ДЛЯ ОТПРАВКИ СТИКЕРА ==========
async def send_enderia_sticker(message: Message, emotion: str = None):
    if emotion and emotion in ENDERIA_STICKERS:
        sticker_id = ENDERIA_STICKERS[emotion]
    else:
        sticker_id = random.choice(list(ENDERIA_STICKERS.values()))
    
    await bot.send_sticker(chat_id=message.chat.id, sticker=sticker_id)

def get_emotion_from_text(text):
    text_lower = text.lower()
    # Вопросы "как дела" и "что делаешь" вызывают безумие
    if any(w in text_lower for w in ["как дел", "что дела", "как ты", "чё дела", "как жизнь", "как настроение"]):
        return "crazy"
    if any(w in text_lower for w in ["люблю", "сердеч", "❤", "💜"]):
        return "heart"
    if any(w in text_lower for w in ["смех", "хаха", "лол", "смеш", "ржу"]):
        return "laugh"
    if any(w in text_lower for w in ["плач", "груст", "печал", "обид"]):
        return "cry"
    if any(w in text_lower for w in ["зл", "бес", "разозл"]):
        return "angry"
    if any(w in text_lower for w in ["телепорт", "прыг", "скак"]):
        return "teleport"
    if any(w in text_lower for w in ["дума", "хмм", "стран", "а?"]):
        return "think"
    if any(w in text_lower for w in ["спать", "сон", "устал"]):
        return "sleep"
    return None

def is_question_about_how_are_you(text):
    """Проверка на вопросы 'как дела' и 'что делаешь'"""
    text_lower = text.lower()
    keywords = ["как дел", "что дела", "как ты", "чё дела", "как жизнь", "как настроение", "как сама", "что нового"]
    return any(keyword in text_lower for keyword in keywords)

def should_respond_to_enderia(message_text):
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "ендер", "энд", "эндер тян"]
    return any(keyword in text_lower for keyword in keywords)

# ========== ЭНДЕРИЯ (GEMINI) ==========
async def get_enderia_response(user_message, username):
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        online = await get_server_online()
        java_online = online.get("java", {}).get("online", 0)
        
        # Добавляем пометку если это вопрос "как дела"
        how_are_you_note = ""
        if is_question_about_how_are_you(user_message):
            how_are_you_note = "\n\nВАЖНО!!! Это вопрос про дела/состояние/занятия! ОТВЕЧАЙ ПАНИЧЕСКИ, КРИЧА, ТЕЛЕПОРТИРУЯСЬ! Используй много восклицательных знаков и эмодзи!"
        
        full_instruction = f"""{SYSTEM_PROMPT}

Текущая дата и время: {current_time}
Сейчас на сервере онлайн: {java_online} игроков.
Игрок {username} написал: "{user_message}"
{how_are_you_note}

Ответь как Эндерия (мило, с эмодзи):"""

        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.95,  # Повышаем для более безумных ответов
            ),
        )
        
        if response.text:
            return response.text
        return None
        
    except Exception as e:
        print(f"Gemini ошибка: {e}")
        return None

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            ),
            InlineKeyboardButton(
                text="ЭНДЕРИЯ", 
                callback_data="menu_enderia",
                icon_custom_emoji_id=EMOJI["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = (
        f"{emoji(EMOJI['start'], '✨')} <b>Добро пожаловать на {SERVER['name']}</b>\n\n"
        f"{emoji(EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{emoji(EMOJI['cat_ok'], '🐱')} <b>Используйте кнопки ниже</b>\n\n"
        f"{endi_emoji(ENDERIA_EMOJI['cat_dance'], '💜')} <i>Я Эндерия - напиши моё имя, и я отвечу!</i>\n"
        f"{endi_emoji(ENDERIA_EMOJI['cat_surprised'], '🤪')} <i>Но осторожно: если спросишь КАК ДЕЛА - я сорвусь в безумие!</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n"
        f"Java: {java_online}/{java_max}",
        parse_mode="HTML"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    if should_respond_to_enderia(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        username = message.from_user.first_name or "Игрок"
        
        # Определяем эмоцию для стикера
        emotion = get_emotion_from_text(message.text)
        await send_enderia_sticker(message, emotion)
        
        # Получаем текстовый ответ
        response = await get_enderia_response(message.text, username)
        
        if response:
            await message.reply(response, parse_mode="HTML")
        else:
            await message.reply(
                f"{endi_emoji(ENDERIA_EMOJI['cat_surprised'], '😲')} Телепортация сломалась... Попробуй ещё раз!",
                parse_mode="HTML"
            )

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{emoji(EMOJI['cat_dance'], '✨')} <b>Главное меню</b>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{emoji(EMOJI['cat_glasses'], '🔄')} <i>Загрузка...</i>",
        parse_mode="HTML"
    )
    
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    
    status = "ONLINE" if java_online > 0 else "OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
- IP: <code>{SERVER['java_ip']}</code>
- Порт: <code>{SERVER['java_port']}</code>
- Версия: <code>{SERVER['java_versions']}</code>
- Онлайн: <b>{java_online}/{java_max}</b>

<b>BEDROCK EDITION</b>
- IP: <code>{SERVER['bedrock_ip']}</code>
- Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    
    status = "ONLINE" if java_online > 0 else "OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
- IP: <code>{SERVER['java_ip']}</code>
- Порт: <code>{SERVER['java_port']}</code>
- Версия: <code>{SERVER['java_versions']}</code>
- Онлайн: <b>{java_online}/{java_max}</b>

<b>BEDROCK EDITION</b>
- IP: <code>{SERVER['bedrock_ip']}</code>
- Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['check'], '✅')} Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '🐱')}{emoji(EMOJI['anime_dance'], '💃')}{emoji(EMOJI['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

{emoji(EMOJI['crown'], '👑')} <b>Привилегии:</b>
- Эксклюзивные ивенты
- Кастомные эмоции в чате
- Приоритетная поддержка
- Уникальный префикс

{emoji(EMOJI['cat_ok'], '📋')} <b>ДОНАТЫ:</b>

🌿 <b>Друид</b> - 25грн / 50руб
🔮 <b>Оракул</b> - 50грн / 100руб
👑 <b>Монарх</b> - 100грн / 200руб
🪽 <b>Херувим</b> - 150грн / 300руб
🏛️ <b>Архонт</b> - 200грн / 400руб
😇 <b>Серафим</b> - 300грн / 600руб

{emoji(EMOJI['check'], '✅')} <b>Оплата:</b> Гривны / Рубли

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>По всем вопросам:</b> @pelmewki379
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""
{endi_emoji(ENDERIA_EMOJI['cat_dance'], '💜')} <b>Кто такая Эндерия?</b>

{endi_emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} Я девушка-эндермен, хранительница Края!

{endi_emoji(ENDERIA_EMOJI['cat_glasses'], '😎')} <b>Мои фишки:</b>
- Обожаю телепортироваться и собирать эндер-жемчуг
- Использую специальные эмодзи котиков, аниме и зайчиков
- Отправляю стикеры по настроению

{endi_emoji(ENDERIA_EMOJI['cat_surprised'], '🤪')} <b>ВАЖНО:</b>
Если спросишь меня <i>КАК ДЕЛА</i> или <i>ЧТО ДЕЛАЮ</i> - Я СОЙДУ С УМА!
Начну телепортироваться, кричать и создавать фиолетовое безумие!

{endi_emoji(ENDERIA_EMOJI['rabbit_fly'], '🐰')} <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Энд, Ендер

{endi_emoji(ENDERIA_EMOJI['cat_kiss'], '😘')} <i>Попробуй спросить меня "Энди, как дела?" - и увидишь безумие!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 50)
    print("БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"Правила: {RULES_URL}")
    print(f"Заявка: {APPLY_URL}")
    print("Эндерия использует СПЕЦИАЛЬНЫЕ ЭМОДЗИ!")
    print("На вопросы 'как дела' Энди СХОДИТ С УМА!")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
