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
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

from prompts import ENDERIA_PROMPT

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

# Инициализация Gemini
ai_client = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini AI подключен!")
    except Exception as e:
        print(f"❌ Ошибка Gemini: {e}")

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
    "java_versions": "1.21 - 1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

online_cache = {}
last_update = {}

# ========== ФУНКЦИЯ ПОЛУЧЕНИЯ ОНЛАЙНА (РАБОЧАЯ) ==========
async def get_minecraft_online():
    """Получает реальный онлайн сервера"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((SERVER["java_ip"], SERVER["java_port"]))
        
        # Отправляем handshake
        handshake = bytearray()
        handshake += b'\x00'  # packet id
        handshake += b'\x04\x00\x00\x00'  # protocol version (754)
        host_bytes = SERVER["java_ip"].encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', SERVER["java_port"])
        handshake += b'\x01'  # next state: status
        
        # Отправляем длину и данные
        sock.send(struct.pack('>i', len(handshake)))
        sock.send(handshake)
        
        # Request
        sock.send(b'\x00\x00')  # length 0, packet id 0
        
        # Читаем ответ
        data = b''
        while len(data) < 5:
            data += sock.recv(1024)
        
        length = struct.unpack('>i', data[:4])[0]
        data = data[4:]
        
        while len(data) < length:
            data += sock.recv(1024)
        
        sock.close()
        
        # Парсим JSON
        data = data[1:]  # пропускаем packet id
        json_data = json.loads(data.decode('utf-8'))
        players = json_data.get("players", {})
        online = players.get("online", 0)
        max_players = players.get("max", 0)
        
        return online, max_players
    except Exception as e:
        print(f"Ошибка получения онлайна: {e}")
        return 0, 0

async def get_server_online():
    """Кэшированный онлайн"""
    now = datetime.now().timestamp()
    if "online" in last_update and now - last_update["online"] < 30:
        return online_cache.get("online", 0), online_cache.get("max", 0)
    
    online, max_players = await get_minecraft_online()
    online_cache["online"] = online
    online_cache["max"] = max_players
    last_update["online"] = now
    return online, max_players

# ========== ЭНДЕРИЯ (GEMINI) ==========
async def get_enderia_response(user_message, username):
    if not ai_client:
        return None
    
    try:
        # Получаем РЕАЛЬНЫЙ онлайн
        online, max_players = await get_server_online()
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        full_instruction = f"""{ENDERIA_PROMPT}

ВАЖНАЯ ИНФОРМАЦИЯ ПРЯМО СЕЙЧАС:
- Текущая дата и время: {current_time}
- Реальный онлайн на сервере LostEarth ПРЯМО СЕЙЧАС: {online} игроков (максимум {max_players})
- Если игрок спрашивает про онлайн - назови точную цифру {online}
- Если онлайн 0 - скажи что сервер пустует, можно заходить первым

Игрок {username} написал: "{user_message}"

ОТВЕТЬ КАК ЭНДЕРИЯ:
- Обязательно используй премиум эмодзи (котик танцует, аниме, зайчик)
- Отвечай коротко и мило
- Если спрашивают про онлайн - скажи что сейчас {online} игроков
- Будь живой и эмоциональной
- Не пиши длинные тексты, 2-3 предложения максимум"""

        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=ai_types.GenerateContentConfig(
                system_instruction=full_instruction,
                temperature=0.9,
            ),
        )
        
        if response.text:
            return response.text
        return None
        
    except Exception as e:
        print(f"Gemini ошибка: {e}")
        return None

def should_respond_to_enderia(message_text):
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)

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
        f"{emoji(EMOJI['cat_ok'], '🐱')} <b>Я Эндерия - напиши моё имя, и я отвечу с премиум эмодзи!</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    status = "🟢 РАБОТАЕТ" if online > 0 else "🔴 ОФФЛАЙН"
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n"
        f"Статус: {status}\n"
        f"Java: {online}/{max_players}\n\n"
        f"{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Присоединяйся к игре!</i>",
        parse_mode="HTML"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    if should_respond_to_enderia(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        username = message.from_user.first_name or "Игрок"
        response = await get_enderia_response(message.text, username)
        
        if response:
            await message.reply(response, parse_mode="HTML")
        else:
            await message.reply(
                f"{emoji(EMOJI['cat_surprised'], '😲')} Телепортация сломалась... Попробуй ещё раз! {emoji(EMOJI['cat_kiss'], '💜')}",
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
        f"{emoji(EMOJI['cat_glasses'], '🔄')} <i>Получаю информацию...</i>",
        parse_mode="HTML"
    )
    
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{online}/{max_players}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    
    online, max_players = await get_server_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{online}/{max_players}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
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
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '💜')} <b>Кто такая Эндерия?</b>

{emoji(EMOJI['cat_ok'], '🐱')} Я девушка-эндермен, хранительница Края!

{emoji(EMOJI['cat_glasses'], '😎')} <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Энд, Ендер

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Просто упомяни моё имя в сообщении, и я отвечу с премиум эмодзи!</i>
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
    print("💜 Эндерия использует ПРЕМИУМ ЭМОДЗИ и реальный ОНЛАЙН!")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
