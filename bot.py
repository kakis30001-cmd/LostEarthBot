import asyncio
import logging
import os
import socket
import struct
import json
from threading import Thread

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from google.genai import types

# ========== НАСТРОЙКА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

# ========== НАСТРОЙКА GEMINI ==========
GEMINI_AVAILABLE = False
gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        logger.info("✅ Gemini AI клиент создан!")
        
        # ПРАВИЛЬНАЯ МОДЕЛЬ - gemini-1.5-flash (работает 100%)
        logger.info("🔄 Тестируем модель gemini-1.5-flash...")
        test_response = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents='Скажи "Привет, я работаю!"'
        )
        logger.info(f"✅ Gemini тест пройден! Ответ: {test_response.text}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini: {e}")
        GEMINI_AVAILABLE = False
else:
    logger.error("❌ GEMINI_API_KEY не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

@flask_app.route('/')
def index():
    return send_from_directory('static', 'rules.html')

@flask_app.route('/apply')
def apply():
    return send_from_directory('static', 'apply.html')

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ========== КОНФИГУРАЦИЯ ==========
SERVER_JAVA_IP = "150.241.85.40"
SERVER_JAVA_PORT = 25565
SERVER_BEDROCK_IP = "150.241.85.40"
SERVER_BEDROCK_PORT = 19132
SERVER_VERSION = "1.21—1.26+"
ADMIN_CONTACT = "@pelmewki379"

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

# ========== ПРЕМИУМ ЭМОДЗИ (ВСЕ ТВОИ) ==========
EMOJI_IDS = {
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

# ========== ПОЛУЧЕНИЕ ОНЛАЙНА ==========
async def get_minecraft_online():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((SERVER_JAVA_IP, SERVER_JAVA_PORT))
        
        handshake = bytearray()
        handshake += b'\x00'
        handshake += b'\x04\x00\x00\x00'
        host_bytes = SERVER_JAVA_IP.encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', SERVER_JAVA_PORT)
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
        return players.get("online", 0)
    except Exception as e:
        logger.error(f"Ошибка онлайна: {e}")
        return 0

# ========== ЭНДЕРИЯ С GEMINI (ИСПРАВЛЕННАЯ МОДЕЛЬ) ==========
async def get_enderia_response(user_message, username):
    if not GEMINI_AVAILABLE or not gemini_client:
        logger.error("❌ Gemini не доступен!")
        return None
    
    try:
        logger.info(f"🤖 Запрос к Gemini от {username}: {user_message[:100]}")
        
        prompt = f"""Ты - Эндерия, девушка-эндермен в чате Minecraft сервера LostEarth.

Твой характер: добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации. Обожаешь котиков, аниме и зайчиков. Любишь шутить про телепортацию.

Твой стиль: используй эмодзи 💜 🟣 🌌 ✨ 🐱 🐰 💃. Любимые слова: телепортну, фиолетово, жемчужку. Обращайся к игроку по имени. Отвечай коротко, 2-3 предложения.

Игрок {username} написал: "{user_message}"

Ответь как Эндерия (мило, с эмодзи, с юмором):"""
        
        # ИСПРАВЛЕНО: правильная модель gemini-1.5-flash
        response = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=150,
            )
        )
        
        if response and response.text:
            logger.info(f"✅ Ответ получен: {response.text[:50]}...")
            return response.text.strip()
        else:
            logger.error("❌ Пустой ответ от Gemini")
            return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini: {e}")
        return None

def should_respond(message_text):
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "эндер тян", "@энд", "ендер", "ендеря"]
    return any(k in text_lower for k in keywords)

# ========== КЛАВИАТУРЫ С ПРЕМИУМ ЭМОДЗИ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['door'], '🌐')} IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI_IDS["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['note'], '📜')} ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI_IDS["note"]
            ),
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['rabbit_fly'], '📝')} ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI_IDS["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['cat_dance'], '💎')} ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI_IDS["cat_dance"]
            ),
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['cat_ok'], '🤖')} ЭНДЕРИЯ", 
                callback_data="menu_enderia",
                icon_custom_emoji_id=EMOJI_IDS["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['check'], '🔄')} ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI_IDS["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI_IDS['back'], '◀️')} НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI_IDS["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    status = "✅" if GEMINI_AVAILABLE else "❌"
    text = f"""{emoji(EMOJI_IDS['start'], '✨')} <b>Добро пожаловать на LostEarth!</b>

{emoji(EMOJI_IDS['house'], '🏠')} <b>Мирный режим по заявкам!</b>

{emoji(EMOJI_IDS['cat_ok'], '🐱')} <b>Я Эндерия - твой AI-помощник!</b>

🤖 <b>Статус ИИ:</b> {status}

💜 Напиши <b>Эндерия</b> или <b>Энди</b> в сообщении, и я отвечу!"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(f"{emoji(EMOJI_IDS['joystick'], '📊')} <b>Онлайн: {online}</b> игроков!", parse_mode="HTML")

@dp.message(Command("ai"))
async def cmd_ai(message: Message):
    if GEMINI_AVAILABLE:
        await message.reply("✅ <b>Gemini AI активен!</b>\n\nЭндерия готова к общению! 💜", parse_mode="HTML")
    else:
        await message.reply("❌ <b>Gemini AI не подключен!</b>\n\nДобавь переменную GEMINI_API_KEY в Railway", parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    if should_respond(message.text):
        logger.info(f"🔔 Обращение к Эндерии от {message.from_user.first_name}")
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            username = message.from_user.first_name or "Игрок"
            response = await get_enderia_response(message.text, username)
            
            if response:
                await message.reply(response, parse_mode="HTML")
            else:
                await message.reply(
                    f"{emoji(EMOJI_IDS['cat_surprised'], '😲')} Ой, телепортация сломалась... Попробуй ещё раз! 💜",
                    parse_mode="HTML"
                )

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(f"{emoji(EMOJI_IDS['cat_dance'], '✨')} <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI_IDS['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI_IDS['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI_IDS['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI_IDS['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{emoji(EMOJI_IDS['cat_dance'], '🐱')}{emoji(EMOJI_IDS['anime_dance'], '💃')}{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 25₴ / 50₽
🔮 Оракул - 50₴ / 100₽
👑 Монарх - 100₴ / 200₽
🪽 Херувим - 150₴ / 300₽
🏛️ Архонт - 200₴ / 400₽
😇 Серафим - 300₴ / 600₽

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} По вопросам: {ADMIN_CONTACT}"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{emoji(EMOJI_IDS['back'], '◀️')} НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI_IDS["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    status = "✅ работает" if GEMINI_AVAILABLE else "❌ не подключен"
    text = f"""{emoji(EMOJI_IDS['cat_dance'], '💜')} <b>Привет! Я Эндерия!</b>

{emoji(EMOJI_IDS['cat_ok'], '🐱')} <b>Кто я:</b> девушка-эндермен, хранительница Края.

🤖 <b>Статус ИИ:</b> {status}

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Эндер-тян

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Попробуй написать "Эндерия, привет!"</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{emoji(EMOJI_IDS['back'], '◀️')} НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI_IDS["back"])]]))
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("=" * 50)
    logger.info("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    logger.info(f"🤖 Gemini: {'✅ ДОСТУПЕН' if GEMINI_AVAILABLE else '❌ НЕТ'}")
    if GEMINI_AVAILABLE:
        logger.info("💜 Эндерия использует модель gemini-1.5-flash")
    else:
        logger.warning("⚠️ Добавь GEMINI_API_KEY в Railway!")
    logger.info("=" * 50)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
