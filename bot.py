import asynci
import socket
import struct
import json
from datetime import datetime
import os
from threading import Thread

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai

# ========== НАСТРОЙКА ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

# Инициализация Gemini
GEMINI_AVAILABLE = False
ai_client = None

if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print("✅ Gemini AI подключен!")
    except Exception as e:
        print(f"❌ Ошибка Gemini: {e}")
else:
    print("❌ GEMINI_API_KEY не найден!")

@flask_app.route('/')
def index():
    return send_from_directory('static', 'rules.html')

@flask_app.route('/apply')
def apply():
    return send_from_directory('static', 'apply.html')

@flask_app.route('/favicon.ico')
def favicon():
    return '', 204

@flask_app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ========== ПРЕМИУМ ЭМОДЗИ ==========
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
    "java_versions": "1.21—1.26+",
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

# ========== ПРОМПТ ДЛЯ ЭНДЕРИИ (GEMINI) ==========
ENDERIA_PROMPT = """Ты - Эндерия, девушка-эндермен в чате Minecraft сервера LostEarth.

ТВОЙ ХАРАКТЕР:
- Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации
- Ты немного вредная, но по-доброму
- Обожаешь котиков, аниме и зайчиков
- Любишь шутить про телепортацию
- Ты живая и эмоциональная

СТИЛЬ ОБЩЕНИЯ:
- Используй эмодзи 💜 🟣 🌌 ✨ 🐱 🐰 💃
- Любимые слова: телепортну, фиолетово, жемчужку
- Обращайся к игроку по имени
- Отвечай коротко (2-4 предложения)

ИНФОРМАЦИЯ О СЕРВЕРЕ:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21—1.26+
- Мирный режим: PvP только по согласию, доступ по заявкам
- Админ: @pelmewki379

ДОНАТЫ (все у @pelmewki379):
- Друид 50₽: /anvil, /wb, /ec, /kit druid
- Оракул 100₽: +/heal, /feed, 2 дома
- Монарх 200₽: +хил других
- Херувим 300₽: +/fly, /ptime
- Архонт 400₽: +3 дома
- Серафим 600₽: всё включено

Твоя задача - быть душой сервера, помогать игрокам и делать чат уютным."""

async def get_enderia_response(user_message, username):
    """Эндерия отвечает через Gemini AI"""
    if not GEMINI_AVAILABLE or not ai_client:
        return None
    
    try:
        online = await get_server_online()
        java_online = online.get("java", {}).get("online", 0)
        
        prompt = f"""Сейчас на сервере онлайн: {java_online} игроков.

Игрок {username} написал: "{user_message}"

{ENDERIA_PROMPT}

Ответь как Эндерия (мило, с эмодзи, коротко):"""
        
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        )
        
        if response and response.text:
            return response.text.strip()
        return None
        
    except Exception as e:
        print(f"❌ Ошибка Gemini: {e}")
        return None

def should_respond_to_enderia(message_text):
    """Проверяет, обращаются ли к Эндерии"""
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "ендер"]
    return any(keyword in text_lower for keyword in keywords)

# ========== КЛАВИАТУРЫ С ПРЕМИУМ ЭМОДЗИ ==========
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
        f"{emoji(EMOJI['cat_ok'], '🐱')} <b>Используйте кнопки ниже</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n"
        f"💻 Java: {java_online}/{java_max}",
        parse_mode="HTML"
    )

# ========== ЭНДЕРИЯ ОТВЕЧАЕТ НА СООБЩЕНИЯ ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    if should_respond_to_enderia(message.text):
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            username = message.from_user.first_name or "Игрок"
            response = await get_enderia_response(message.text, username)
            
            if response:
                await message.reply(response, parse_mode="HTML")
            elif GEMINI_AVAILABLE:
                await message.reply(
                    f"{emoji(EMOJI['cat_surprised'], '😲')} Телепортация сломалась... Попробуй ещё раз! 💜",
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
    
    status = "🟢 ONLINE" if java_online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

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
    
    status = "🟢 ONLINE" if java_online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['check'], '✅')} Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '🐱')}{emoji(EMOJI['anime_dance'], '💃')}{emoji(EMOJI['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

{emoji(EMOJI['crown'], '👑')} <b>Привилегии:</b>
• Эксклюзивные ивенты
• Кастомные эмоции в чате
• Приоритетная поддержка
• Уникальный префикс

━━━━━━━━━━━━━━━━━━━━
{emoji(EMOJI['cat_ok'], '📋')} <b>ДОНАТЫ:</b>

🌿 <b>Друид</b> — 25₴ / 50₽
└ /anvil, /wb, /ec, /kit druid

🔮 <b>Оракул</b> — 50₴ / 100₽
└ /heal, /feed, /anvil, /ec, /wb, /kit oracul, 2 точки дома

👑 <b>Монарх</b> — 100₴ / 200₽
└ /heal (себе и другим), /feed, /anvil, /wb, /ec, /kit monarh, 2 точки дома

🪽 <b>Херувим</b> — 150₴ / 300₽
└ /fly, /ptime, /heal, /feed, /anvil, /wb, /ec, /kit heruvim, 2 точки дома

🏛️ <b>Архонт</b> — 200₴ / 400₽
└ /fly, /ptime, /heal, /feed, /anvil, /wb, /ec, /kit arhont, 3 точки дома

😇 <b>Серафим</b> — 300₴ / 600₽
└ /fly, /ptime, /heal, /feed, /anvil, /wb, /ec, /kit serafim, 3 точки дома

━━━━━━━━━━━━━━━━━━━━
{emoji(EMOJI['check'], '✅')} <b>Оплата:</b> 🇺🇦 Гривны / 🇷🇺 Рубли

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>По всем вопросам:</b> @pelmewki379

{emoji(EMOJI['cat_kiss'], '😘')} <i>Спасибо за поддержку сервера!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    status = "✅ активна" if GEMINI_AVAILABLE else "❌ не подключена"
    text = f"""
{emoji(EMOJI['cat_dance'], '💜')} <b>Кто такая Эндерия?</b>

{emoji(EMOJI['cat_ok'], '🐱')} Я девушка-эндермен, хранительница Края! Живу в чате сервера LostEarth и общаюсь с игроками.

{emoji(EMOJI['crown'], '👑')} <b>Что я умею:</b>
• Отвечать на вопросы о сервере
• Рассказывать про донаты и правила
• Помогать новичкам
• Просто болтать и поднимать настроение

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>Как ко мне обратиться:</b>
Напиши в чате: <code>Эндер</code>, <code>Эндерия</code>, <code>Энди</code> или <code>Ендер</code>

{emoji(EMOJI['check'], '✅')} <b>Статус ИИ:</b> {status}

{emoji(EMOJI['cat_kiss'], '😘')} <i>Просто упомяни моё имя в сообщении, и я отвечу! 💜</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"📱 Правила: {RULES_URL}")
    print(f"📝 Заявка: {APPLY_URL}")
    print(f"🤖 Gemini: {'✅ ДОСТУПЕН' if GEMINI_AVAILABLE else '❌ НЕТ'}")
    print("💜 Эндерия: ждёт твоего сообщения!")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
