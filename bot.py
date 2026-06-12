import asyncio
import os
import socket
import struct
import json
from datetime import datetime
from threading import Thread

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from flask import Flask, send_from_directory

from enderia import get_enderia_response, should_respond, emoji, ENDERIA_EMOJI, GEMINI_API_KEYS

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ДЛЯ WEBAPP ==========
app = Flask(__name__, static_folder='.')

@app.route('/')
def serve_rules():
    return send_from_directory('.', 'rules.html')

@app.route('/apply')
def serve_apply():
    return send_from_directory('.', 'apply.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ========== БОТ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ПРЕМИУМ ЭМОДЗИ ==========
PREMIUM_EMOJI = {
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
    "magic": "5474144592817318927",
    "microphone": "5870831513192369918",
    "cat_money": "5267058870580191916",
}

def premium_emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

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

BASE_URL = os.getenv("BASE_URL", "https://your-railway-app.up.railway.app")

online_cache = {}
last_update = {}

# ========== MINECRAFT API ==========
async def get_java_status(ip: str, port: int = 25565):
    try:
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
        return players.get("online", 0), players.get("max", 0)
    except:
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

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['door'], '🚪')} IP И ОНЛАЙН", 
            callback_data="menu_ip"
        )],
        [InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['note'], '📜')} ПРАВИЛА", 
            web_app=WebAppInfo(url=f"{BASE_URL}/rules.html")
        ),
        InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['rabbit_fly'], '📝')} ЗАЯВКА", 
            web_app=WebAppInfo(url=f"{BASE_URL}/apply.html")
        )],
        [InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['cat_dance'], '💎')} ПРЕМИУМ", 
            callback_data="menu_premium"
        ),
        InlineKeyboardButton(
            text=f"{premium_emoji(ENDERIA_EMOJI['heart'], '💜')} ЭНДЕРИЯ", 
            callback_data="menu_enderia"
        )]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['check'], '🔄')} ОБНОВИТЬ", 
            callback_data="refresh_online"
        )],
        [InlineKeyboardButton(
            text=f"{premium_emoji(PREMIUM_EMOJI['back'], '◀️')} НАЗАД", 
            callback_data="menu_main"
        )]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = f"""{premium_emoji(PREMIUM_EMOJI['start'], '✨')} <b>Добро пожаловать на {SERVER['name']}</b>

{premium_emoji(PREMIUM_EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>

{premium_emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} <b>Я Эндерия - напиши моё имя, и я отвечу!</b>

{premium_emoji(ENDERIA_EMOJI['heart'], '💜')} {premium_emoji(ENDERIA_EMOJI['cat_dance'], '💃')}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(
        f"{premium_emoji(PREMIUM_EMOJI['joystick'], '📊')} <b>Онлайн: {online}/{max_players}</b>", 
        parse_mode="HTML"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.first_name or "Игрок"
    
    if should_respond(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(message.text, username)
        
        if response:
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{premium_emoji(PREMIUM_EMOJI['magic'], '✨')} <b>Главное меню</b>", 
        parse_mode="HTML", 
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{premium_emoji(PREMIUM_EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

💻 JAVA: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📊 Онлайн: {online}/{max_players}
📱 BEDROCK: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>

{premium_emoji(PREMIUM_EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры!</i>
{premium_emoji(ENDERIA_EMOJI['heart'], '💜')}"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{premium_emoji(PREMIUM_EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

💻 JAVA: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📊 Онлайн: {online}/{max_players}
📱 BEDROCK: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>

{premium_emoji(PREMIUM_EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры!</i>
{premium_emoji(ENDERIA_EMOJI['heart'], '💜')}"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{premium_emoji(PREMIUM_EMOJI['cat_dance'], '💎')} <b>ПРЕМИУМ ДОСТУП</b>

{premium_emoji(PREMIUM_EMOJI['cat_money'], '🌿')} <b>Друид</b> - 25грн / 50₽
{premium_emoji(PREMIUM_EMOJI['magic'], '🔮')} <b>Оракул</b> - 50грн / 100₽
{premium_emoji(PREMIUM_EMOJI['crown'], '👑')} <b>Монарх</b> - 100грн / 200₽
{premium_emoji(PREMIUM_EMOJI['rabbit_fly'], '🪽')} <b>Херувим</b> - 150грн / 300₽
{premium_emoji(PREMIUM_EMOJI['house'], '🏛️')} <b>Архонт</b> - 200грн / 400₽
{premium_emoji(ENDERIA_EMOJI['cat_dance'], '😇')} <b>Серафим</b> - 300грн / 600₽

📩 По вопросам: @pelmewki379
{premium_emoji(ENDERIA_EMOJI['heart'], '💜')}"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"{premium_emoji(PREMIUM_EMOJI['back'], '◀️')} НАЗАД", 
                callback_data="menu_main"
            )
        ]])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{premium_emoji(ENDERIA_EMOJI['heart'], '💜')} <b>Эндерия</b>

{premium_emoji(ENDERIA_EMOJI['cat_ok'], '🐱')} Я девушка-эндермен из LostEarth!

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Ендер

{premium_emoji(ENDERIA_EMOJI['rabbit_fly'], '🐰')} <i>Просто позови меня по имени, и я отвечу!</i>
{premium_emoji(ENDERIA_EMOJI['cat_dance'], '💃')}"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"{premium_emoji(PREMIUM_EMOJI['back'], '◀️')} НАЗАД", 
                callback_data="menu_main"
            )
        ]])
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    # Запускаем Flask сервер для WebApp
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"📊 Ключей Gemini: {len(GEMINI_API_KEYS)}")
    print(f"🌐 WebApp URL: {BASE_URL}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
