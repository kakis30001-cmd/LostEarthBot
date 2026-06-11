import asyncio
import socket
import struct
import json
from datetime import datetime
import os
import traceback
from threading import Thread
from collections import deque

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    raise ValueError("❌ BOT_TOKEN не найден!")

# ========== ПАМЯТЬ ЧАТА ==========
chat_memory = deque(maxlen=100)

def add_to_memory(username: str, message: str):
    chat_memory.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "username": username,
        "message": message
    })

def get_chat_context() -> str:
    if not chat_memory:
        return ""
    return "\n".join([f"{msg['username']}: {msg['message']}" for msg in chat_memory])

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

# Gemini инициализация с проверкой
ai_client = None
if GEMINI_API_KEY:
    try:
        print("🔄 Подключение к Gemini API...")
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini AI успешно подключен!")
    except Exception as e:
        print(f"❌ ОШИБКА подключения Gemini: {e}")
        traceback.print_exc()
else:
    print("⚠️ GEMINI_API_KEY не найден! Эндерия не будет отвечать.")

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
    print(f"🔄 Запуск Flask на порту {port}...")
    flask_app.run(host='0.0.0.0', port=port, debug=False)

# ========== ПРЕМИУМ ЭМОДЗИ ==========
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
    "cat_surprised": "5269649173946345008",
}

def emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# ========== КОНФИГУРАЦИЯ ==========
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

# ========== MINECRAFT API ==========
async def get_java_status(ip: str, port: int = 25565):
    try:
        print(f"🔄 Проверка статуса сервера {ip}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
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
        online = players.get("online", 0)
        max_players = players.get("max", 0)
        print(f"📊 Сервер онлайн: {online}/{max_players}")
        return online, max_players
    except Exception as e:
        print(f"❌ Ошибка получения статуса сервера: {e}")
        return 0, 0

async def get_server_online():
    now = datetime.now().timestamp()
    if "online" in last_update and now - last_update["online"] < 30:
        return online_cache.get("online", 0), online_cache.get("max", 0)
    online, max_players = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    online_cache["online"] = online
    online_cache["max"] = max_players
    last_update["online"] = now
    return online, max_players

# ========== ПРОМПТ ==========
ENDERIA_PROMPT = """
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации. Обожаешь котиков, аниме и зайчиков.

Отвечай коротко, 2-4 предложения. Обращайся к игроку по имени. Обязательно используй эмодзи.

Информация о сервере:
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Версия: 1.21-1.26+
- Мирный режим: PvP только по согласию, доступ по заявкам
- Админ: @pelmewki379

Донаты: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽
"""

# ========== ЭНДЕРИЯ ==========
async def get_enderia_response(user_message, username):
    print(f"🔄 Запрос к Gemini от {username}: {user_message[:50]}...")
    
    if not ai_client:
        print("❌ Gemini клиент не инициализирован!")
        return None
    
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        online, _ = await get_server_online()
        chat_context = get_chat_context()
        
        full_instruction = f"""{ENDERIA_PROMPT}

Текущая дата и время: {current_time}
Сейчас на сервере онлайн: {online} игроков.

Недавние сообщения в чате:
{chat_context}

Игрок {username} написал: "{user_message}"

Ответь как Эндерия (мило, с эмодзи, коротко):"""

        print("🔄 Отправка запроса в Gemini...")
        
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.9,
                max_output_tokens=200,
            ),
        )
        
        if response and response.text:
            print(f"✅ Gemini ответил: {response.text[:50]}...")
            return response.text
        else:
            print("⚠️ Gemini вернул пустой ответ")
            return None
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА Gemini: {e}")
        traceback.print_exc()
        return None

def should_respond(message_text):
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(k in text_lower for k in keywords)

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌐 IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="📜 ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="📝 ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            ),
            InlineKeyboardButton(
                text="💜 ЭНДЕРИЯ", 
                callback_data="menu_enderia",
                icon_custom_emoji_id=EMOJI["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    print(f"📨 Команда /start от {message.from_user.id}")
    text = f"""{emoji(EMOJI['start'], '✨')} <b>Добро пожаловать на {SERVER['name']}</b>

{emoji(EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>

{emoji(EMOJI['cat_ok'], '🐱')} <b>Я Эндерия - напиши моё имя, и я отвечу!</b>"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    print(f"📨 Команда /online от {message.from_user.id}")
    online, max_players = await get_server_online()
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n"
        f"Java: {online}/{max_players}",
        parse_mode="HTML"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.first_name or "Игрок"
    print(f"💬 Сообщение от {username}: {message.text[:50]}...")
    
    add_to_memory(username, message.text)
    
    if should_respond(message.text):
        print(f"🔔 Обращение к Эндерии от {username}")
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(message.text, username)
        
        if response:
            print(f"✅ Ответ отправлен {username}")
            await message.reply(response, parse_mode="HTML")
        else:
            print(f"❌ Не удалось получить ответ от Gemini для {username}")
            await message.reply(
                f"{emoji(EMOJI['cat_surprised'], '😲')} Телепортация сломалась... Попробуй ещё раз!",
                parse_mode="HTML"
            )

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text("✨ <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{online}/{max_players}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{online}/{max_players}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{emoji(EMOJI['cat_dance'], '💎')} <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 25грн / 50₽
🔮 Оракул - 50грн / 100₽
👑 Монарх - 100грн / 200₽
🪽 Херувим - 150грн / 300₽
🏛️ Архонт - 200грн / 400₽
😇 Серафим - 300грн / 600₽

📩 По вопросам: @pelmewki379"""
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
    text = f"""{emoji(EMOJI['cat_dance'], '💜')} <b>Эндерия</b>

{emoji(EMOJI['cat_ok'], '🐱')} Я девушка-эндермен из LostEarth!

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Ендер

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Просто позови меня по имени, и я отвечу!</i>"""
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
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 60)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"📱 Правила WebApp: {RULES_URL}")
    print(f"📝 Заявка WebApp: {APPLY_URL}")
    if ai_client:
        print("💜 Эндерия с Gemini AI активна и готова к общению!")
    else:
        print("⚠️ Эндерия отключена (проверь GEMINI_API_KEY в переменных)")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
