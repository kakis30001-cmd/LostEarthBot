import asyncio
import os
import socket
import struct
import json
from datetime import datetime
from threading import Thread
import random

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from flask import Flask, send_from_directory

from enderia import get_enderia_response, should_respond, clear_user_memory, get_memory_size

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ДЛЯ WEBAPP (файлы в папке static) ==========
app = Flask(__name__, static_folder='static', static_url_path='/static')

@app.route('/')
def serve_rules():
    return send_from_directory('static', 'rules.html')

@app.route('/rules.html')
def serve_rules_html():
    return send_from_directory('static', 'rules.html')

@app.route('/apply')
def serve_apply():
    return send_from_directory('static', 'apply.html')

@app.route('/apply.html')
def serve_apply_html():
    return send_from_directory('static', 'apply.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

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
    "cat_up": "5269698007724499331",
    "cat_kiss": "6325462176660195024",
    "heart": "5199427253225667842",
}

def premium_emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def random_cat():
    cats = [PREMIUM_EMOJI["cat_dance"], PREMIUM_EMOJI["cat_ok"], PREMIUM_EMOJI["cat_up"]]
    return premium_emoji(random.choice(cats), "🐱")

def random_rabbit():
    return premium_emoji(PREMIUM_EMOJI["rabbit_fly"], "🐰")

def random_heart():
    return premium_emoji(PREMIUM_EMOJI["heart"], "💜")

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

BASE_URL = os.getenv("BASE_URL", "https://lostearthbot-production.up.railway.app")
RULES_URL = f"{BASE_URL}/rules.html"
APPLY_URL = f"{BASE_URL}/apply.html"

online_cache = {}
last_update = {}
last_online_data = {}

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
        [
            InlineKeyboardButton(
                text="IP И ОНЛАЙН", 
                callback_data="menu_ip", 
                icon_custom_emoji_id=PREMIUM_EMOJI["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL), 
                icon_custom_emoji_id=PREMIUM_EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL), 
                icon_custom_emoji_id=PREMIUM_EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРЕМИУМ", 
                callback_data="menu_premium", 
                icon_custom_emoji_id=PREMIUM_EMOJI["cat_dance"]
            ),
            InlineKeyboardButton(
                text="ЭНДЕРИЯ", 
                callback_data="menu_enderia", 
                icon_custom_emoji_id=PREMIUM_EMOJI["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="ОБНОВИТЬ", 
                callback_data="refresh_online", 
                icon_custom_emoji_id=PREMIUM_EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main", 
                icon_custom_emoji_id=PREMIUM_EMOJI["back"]
            )
        ]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main", 
                icon_custom_emoji_id=PREMIUM_EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = f"""{premium_emoji(PREMIUM_EMOJI['start'], '✨')} <b>Добро пожаловать на {SERVER['name']}</b>

🏠 <b>{SERVER['mode']}</b>

{random_cat()} <b>Я Эндерия - напиши моё имя, и я отвечу!</b>"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(
        f"{premium_emoji(PREMIUM_EMOJI['joystick'], '📊')} <b>Онлайн: {online}/{max_players}</b>", 
        parse_mode="HTML"
    )

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    size = get_memory_size(username)
    
    if size > 0:
        await message.answer(
            f"{random_cat()} <b>{username}, я помню наш диалог!</b>\n\n"
            f"📊 Запомнено сообщений: {size}\n"
            f"💜 Могу ответить на любые вопросы по LostEarth!\n\n"
            f"✨ Если хочешь очистить память - напиши /clear_memory",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{random_heart()} <b>{username}, мы ещё не общались!</b>\n\n"
            f"📝 Напиши что-нибудь с моим именем (Энди, Эндерия, Эндер)\n"
            f"🐱 И я запомню наш разговор!",
            parse_mode="HTML"
        )

@dp.message(Command("clear_memory"))
async def clear_memory_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    old_size = get_memory_size(username)
    clear_user_memory(username)
    await message.answer(
        f"{random_cat()} ✨ <b>Память очищена!</b>\n\n"
        f"📊 Было запомнено: {old_size} сообщений\n"
        f"💜 Теперь можем начать разговор заново!\n\n"
        f"🐰 Напиши что-нибудь, и я познакомлюсь с тобой снова",
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

{random_rabbit()} <i>Приятной игры!</i>"""
    
    last_online_data[callback.message.chat.id] = {
        "online": online,
        "max": max_players,
        "message_id": callback.message.message_id
    }
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{premium_emoji(PREMIUM_EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

💻 JAVA: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📊 Онлайн: {online}/{max_players}
📱 BEDROCK: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>

{random_rabbit()} <i>Приятной игры!</i>"""
    
    chat_id = callback.message.chat.id
    last_data = last_online_data.get(chat_id, {})
    
    if (last_data.get("online") == online and 
        last_data.get("max") == max_players and
        callback.message.text == text):
        await callback.answer("✨ Онлайн не изменился!", show_alert=False)
        return
    
    last_online_data[chat_id] = {
        "online": online,
        "max": max_players,
        "message_id": callback.message.message_id
    }
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer("🔄 Онлайн обновлён!")
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer("✨ Онлайн не изменился!", show_alert=False)
        else:
            await callback.answer("⚠️ Ошибка обновления", show_alert=False)

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""💎 <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 25грн / 50₽
🔮 Оракул - 50грн / 100₽
👑 Монарх - 100грн / 200₽
🪽 Херувим - 150грн / 300₽
🏛️ Архонт - 200грн / 400₽
😇 Серафим - 300грн / 600₽

📩 По вопросам: @pelmewki379"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{random_heart()} <b>Эндерия</b>

{random_cat()} Я девушка-эндермен из LostEarth!

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Ендер

{random_rabbit()} <i>Просто позови меня по имени, и я отвечу!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🎨 Премиум эмодзи загружено: {len(PREMIUM_EMOJI)}")
    print("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        if "Conflict" in str(e):
            print("⚠️ Конфликт бота. Перезапуск через 5 секунд...")
            await asyncio.sleep(5)
            await dp.start_polling(bot)
        else:
            raise e

if __name__ == "__main__":
    asyncio.run(main())
