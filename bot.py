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
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

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

# ========== КОНФИГУРАЦИЯ СЕРВЕРА ==========
SERVER_JAVA_IP = "150.241.85.40"
SERVER_JAVA_PORT = 25565
SERVER_BEDROCK_IP = "150.241.85.40"
SERVER_BEDROCK_PORT = 19132
SERVER_VERSION = "1.21—1.26+"
ADMIN_CONTACT = "@pelmewki379"

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

# ========== ПРЕМИУМ ЭМОДЗИ (ТОЛЬКО ДЛЯ КНОПОК) ==========
EMOJI_IDS = {
    "door": "5873147866364514353",
    "note": "5870930744116776638",
    "rabbit_fly": "5217576088506505749",
    "cat_dance": "5359444458930718519",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
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

# ========== КНОПКИ (ТОЛЬКО ПРЕМИУМ ЭМОДЗИ) ==========
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
    text = f"""{emoji(EMOJI_IDS['start'], '✨')} <b>Добро пожаловать на LostEarth!</b>

{emoji(EMOJI_IDS['house'], '🏠')} <b>Мирный режим по заявкам!</b>

<i>Используйте кнопки ниже для навигации</i>"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(f"{emoji(EMOJI_IDS['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n💻 Сейчас играет: <b>{online}</b> игроков!", parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{emoji(EMOJI_IDS['start'], '✨')} <b>Главное меню</b>", 
        parse_mode="HTML", 
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{emoji(EMOJI_IDS['cat_glasses'], '🔄')} <i>Получаю информацию...</i>",
        parse_mode="HTML"
    )
    
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI_IDS['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI_IDS['house'], '🏠')} <i>Мирный режим по заявкам!</i>

{emoji(EMOJI_IDS['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI_IDS['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI_IDS['house'], '🏠')} <i>Мирный режим по заявкам!</i>

{emoji(EMOJI_IDS['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI_IDS['check'], '✅')} Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI_IDS['cat_dance'], '🐱')}{emoji(EMOJI_IDS['cat_dance'], '💃')}{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

🌿 <b>Друид</b> — 25₴ / 50₽
🔮 <b>Оракул</b> — 50₴ / 100₽
👑 <b>Монарх</b> — 100₴ / 200₽
🪽 <b>Херувим</b> — 150₴ / 300₽
🏛️ <b>Архонт</b> — 200₴ / 400₽
😇 <b>Серафим</b> — 300₴ / 600₽

━━━━━━━━━━━━━━━━━━━━
{emoji(EMOJI_IDS['check'], '✅')} <b>Оплата:</b> 🇺🇦 Гривны / 🇷🇺 Рубли

{emoji(EMOJI_IDS['rabbit_fly'], '🐰')} <b>По вопросам:</b> {ADMIN_CONTACT}

{emoji(EMOJI_IDS['cat_dance'], '😘')} <i>Спасибо за поддержку!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI_IDS["back"])]
        ])
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("=" * 50)
    logger.info("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    logger.info(f"📱 Правила WebApp: {RULES_URL}")
    logger.info(f"📝 Заявка WebApp: {APPLY_URL}")
    logger.info("=" * 50)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
