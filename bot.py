import asyncio
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
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

@flask_app.route('/')
def index():
    return send_from_directory('static', 'rules.html')

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ТОЛЬКО ПРЕМИУМ ЭМОДЗИ
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "cat_dance": "5359444458930718519",
    "cat_kiss": "6325462176660195024",
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

# Сервер
SERVER = {
    "name": "LostEarth",
    "mode": "Мирный режим по заявкам!",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "java_versions": "1.21—1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

RULES_URL = "https://lostearthbot-production.up.railway.app/"

online_cache = {}
last_update = {}

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
                web_app=WebAppInfo(url=f"{RULES_URL}apply.html"),
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
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
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['check'], '✅')} Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['door'], '🚪')} <b>ДОСТУП К МИРНОМУ РЕЖИМУ</b>

{emoji(EMOJI['cat_ok'], '🤙')} <b>Как попасть:</b>

1️⃣ Напишите заявку: @pelmewki379
2️⃣ Расскажите немного о себе
3️⃣ Дождитесь ответа администратора

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>Подать заявку:</b> @pelmewki379

{emoji(EMOJI['cat_kiss'], '😘')} <i>Добро пожаловать на LostEarth!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

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
└ /heal, /feed, /anvil, /ec, /wb, /kit monarh, хил других, 2 точки дома

🪽 <b>Херувим</b> — 150₴ / 300₽
└ /fly, /ptime, /heal, /feed, /ec, /wb, /anvil, /kit heruvim, 2 точки дома

🏛️ <b>Архонт</b> — 200₴ / 400₽
└ /fly, /ptime, /heal, /feed, /ec, /wb, /anvil, /kit arhont, 3 точки дома

😇 <b>Серафим</b> — 300₴ / 600₽
└ /fly, /ptime, /heal, /feed, /ec, /wb, /anvil, /kit serafim, 3 точки дома

━━━━━━━━━━━━━━━━━━━━
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

async def main():
    thread = Thread(target=run_flask)
    thread.start()
    
    print("🚀 Бот LostEarth запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
