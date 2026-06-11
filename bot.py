import asyncio
import logging
import os
import socket
import struct
import json
from threading import Thread
from io import BytesIO

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

# ========== ИНИЦИАЛИЗАЦИЯ GEMINI (ПРАВИЛЬНАЯ) ==========
GEMINI_AVAILABLE = False
gemini_client = None

if GEMINI_API_KEY:
    try:
        # Правильная инициализация клиента
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        logger.info("✅ Gemini AI клиент создан!")
    except Exception as e:
        logger.error(f"❌ Ошибка создания клиента Gemini: {e}")
else:
    logger.error("❌ GEMINI_API_KEY не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
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

# ========== ПРЕМИУМ ЭМОДЗИ ==========
EMOJI_IDS = {
    "door": "5873147866364514353",
    "note": "5870930744116776638",
    "rabbit_fly": "5217576088506505749",
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "cat_glasses": "5267088110717544191",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "start": "5870921127685001066",
    "cat_surprised": "5269649173946345008",
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

# ========== ЭНДЕРИЯ С GEMINI (ИСПРАВЛЕННАЯ) ==========
async def get_enderia_response(user_message, username, photo_data=None):
    if not GEMINI_AVAILABLE or not gemini_client:
        logger.error("❌ Gemini не доступен!")
        return None
    
    try:
        logger.info(f"🤖 Запрос к Gemini от {username}: {user_message[:50] if user_message else 'фото'}")
        
        # Формируем промпт
        prompt = f"""Ты - Эндерия, девушка-эндермен в чате Minecraft сервера LostEarth.

Твой характер: добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации. Обожаешь котиков, аниме и зайчиков.

Твой стиль: используй эмодзи 💜 🟣 🌌 ✨ 🐱 🐰 💃. Обращайся к игроку по имени. Отвечай коротко, 2-3 предложения.

Игрок {username} написал: {user_message if user_message else 'Отправил фото'}

Ответь как Эндерия (мило, с эмодзи):"""
        
        # Если есть фото, отправляем с ним
        if photo_data:
            response = gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[prompt, photo_data]
            )
        else:
            response = gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
        
        if response and response.text:
            logger.info(f"✅ Ответ получен")
            return response.text.strip()
        else:
            logger.error("❌ Пустой ответ")
            return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini: {e}")
        return f"🛠 Техническая ошибка:\n{e}"

def should_respond(message_text):
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "ендер"]
    return any(k in text_lower for k in keywords)

# ========== КНОПКИ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI_IDS["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI_IDS["note"]
            ),
            InlineKeyboardButton(
                text="ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI_IDS["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI_IDS["cat_dance"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI_IDS["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI_IDS["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = f"""✨ <b>Добро пожаловать на LostEarth!</b>

🏠 <b>Мирный режим по заявкам!</b>

🐱 <b>Я Эндерия - твой помощник!</b>

💜 Напиши моё имя в сообщении, и я отвечу!"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(f"📊 <b>Онлайн: {online}</b> игроков!", parse_mode="HTML")

# Обработчик текстовых сообщений
@dp.message()
async def handle_message(message: Message):
    if should_respond(message.text):
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            username = message.from_user.first_name or "Игрок"
            response = await get_enderia_response(message.text, username)
            
            if response:
                await message.reply(response, parse_mode="HTML")
            else:
                await message.reply(
                    "😲 Ой, телепортация сломалась... Попробуй ещё раз! 💜",
                    parse_mode="HTML"
                )

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text("✨ <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text("🔄 <i>Получаю информацию...</i>", parse_mode="HTML")
    
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""👑 <b>LOSTEARTH</b> | {status}

🏠 <i>Мирный режим по заявкам!</i>

💻 <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

🐰 <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""👑 <b>LOSTEARTH</b> | {status}

🏠 <i>Мирный режим по заявкам!</i>

💻 <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

🐰 <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"✅ Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""🐱💃🐰 <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 25₴ / 50₽
🔮 Оракул - 50₴ / 100₽
👑 Монарх - 100₴ / 200₽
🪽 Херувим - 150₴ / 300₽
🏛️ Архонт - 200₴ / 400₽
😇 Серафим - 300₴ / 600₽

🐰 По вопросам: @pelmewki379"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI_IDS["back"])]
    ]))
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("=" * 50)
    logger.info("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    logger.info(f"🤖 Gemini: {'✅ ДОСТУПЕН' if GEMINI_AVAILABLE else '❌ НЕТ'}")
    if GEMINI_AVAILABLE:
        logger.info("💜 Эндерия готова к общению!")
    else:
        logger.warning("⚠️ Добавь GEMINI_API_KEY в Railway!")
    logger.info("=" * 50)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
