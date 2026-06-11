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
        logger.info("✅ Gemini AI готов!")
        
        # Тестовый запрос
        test_response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents='Скажи "OK"'
        )
        logger.info(f"✅ Тест Gemini прошёл: {test_response.text}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini: {e}")
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
ADMIN_CONTACT = "@pelmewki379"

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

# ========== ЭМОДЗИ ==========
EMOJI = {
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

# ========== ЭНДЕРИЯ (ИСПРАВЛЕННЫЙ GEMINI) ==========
async def get_enderia_response(user_message, username):
    if not GEMINI_AVAILABLE or not gemini_client:
        logger.error("Gemini не доступен!")
        return None
    
    try:
        logger.info(f"🤖 Запрос к Gemini от {username}: {user_message[:50]}")
        
        # Правильный формат промпта
        prompt = f"""Ты - Эндерия, девушка-эндермен в чате Minecraft сервера LostEarth. 
Ты добрая, любишь шутить про телепортацию. Отвечай коротко и весело.

Игрок {username} спрашивает: {user_message}

Твой ответ (с эмодзи 💜🐱):"""
        
        # Правильный вызов API
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=150,
            )
        )
        
        # Получаем текст ответа
        if response and response.text:
            result = response.text.strip()
            logger.info(f"✅ Ответ: {result[:50]}...")
            return result
        else:
            logger.error("❌ Пустой ответ от Gemini")
            return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini: {e}")
        return None

def should_respond(message_text):
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "эндер тян", "@энд"]
    return any(k in text_lower for k in keywords)

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 IP И ОНЛАЙН", callback_data="menu_ip", icon_custom_emoji_id=EMOJI["door"])],
        [
            InlineKeyboardButton(text="📜 ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL), icon_custom_emoji_id=EMOJI["note"]),
            InlineKeyboardButton(text="📝 ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL), icon_custom_emoji_id=EMOJI["rabbit_fly"])
        ],
        [
            InlineKeyboardButton(text="💎 ПРЕМИУМ", callback_data="menu_premium", icon_custom_emoji_id=EMOJI["cat_dance"]),
            InlineKeyboardButton(text="🤖 ЭНДЕРИЯ", callback_data="menu_enderia", icon_custom_emoji_id=EMOJI["cat_ok"])
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ОБНОВИТЬ", callback_data="refresh_online", icon_custom_emoji_id=EMOJI["check"])],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    status = "✅" if GEMINI_AVAILABLE else "❌"
    text = f"""{emoji(EMOJI['start'], '✨')} <b>Добро пожаловать на LostEarth!</b>

{emoji(EMOJI['house'], '🏠')} <b>Мирный режим по заявкам!</b>

🤖 <b>Статус ИИ:</b> {status}

💜 Напиши <b>Эндерия</b> или <b>Энди</b> в сообщении, и я отвечу!"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(f"📊 <b>Онлайн: {online}</b> игроков!", parse_mode="HTML")

@dp.message(Command("ai"))
async def cmd_ai(message: Message):
    if GEMINI_AVAILABLE:
        await message.reply("✅ <b>Gemini AI активен!</b>\n\nЭндерия готова к общению! Просто напиши её имя в сообщении 💜", parse_mode="HTML")
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
                await message.reply("😲 Ой, телепортация сломалась... Попробуй позже! 💜", parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text("✨ <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online = await get_minecraft_online()
    text = f"""👑 <b>LOSTEARTH</b> | {'🟢 ONLINE' if online > 0 else '🔴 OFFLINE'}

💻 <b>JAVA</b> — <code>{SERVER_JAVA_IP}:{SERVER_JAVA_PORT}</code>
📱 <b>BEDROCK</b> — <code>{SERVER_BEDROCK_IP}:{SERVER_BEDROCK_PORT}</code>
📊 <b>Онлайн:</b> {online} игроков"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    text = f"""👑 <b>LOSTEARTH</b> | {'🟢 ONLINE' if online > 0 else '🔴 OFFLINE'}

💻 <b>JAVA</b> — <code>{SERVER_JAVA_IP}:{SERVER_JAVA_PORT}</code>
📱 <b>BEDROCK</b> — <code>{SERVER_BEDROCK_IP}:{SERVER_BEDROCK_PORT}</code>
📊 <b>Онлайн:</b> {online} игроков"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""💎 <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 50₽
🔮 Оракул - 100₽
👑 Монарх - 200₽
🪽 Херувим - 300₽
🏛️ Архонт - 400₽
😇 Серафим - 600₽

🐰 По вопросам: {ADMIN_CONTACT}"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    status = "✅ работает" if GEMINI_AVAILABLE else "❌ не подключен"
    text = f"""💜 <b>Привет! Я Эндерия!</b>

🤖 Статус ИИ: {status}

💬 Напиши: Эндер, Эндерия, Энди, Эндер-тян"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]]))
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("=" * 40)
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info(f"🤖 Gemini: {'✅ ДОСТУПЕН' if GEMINI_AVAILABLE else '❌ НЕТ'}")
    if GEMINI_AVAILABLE:
        logger.info("💜 Эндерия готова отвечать!")
    logger.info("=" * 40)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
