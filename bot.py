import asyncio
import socket
import struct
import json
from datetime import datetime
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Эмодзи (рабочие ID из твоего примера)
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "rabbit_smile": "5219869124301199449",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "cat_kiss": "6325462176660195024",
    "cat_surprised": "5242261773817492813",
    "cat_dance": "5359444458930718519",
    "house": "5873147866364514353",
    "microphone": "5870831513192369918",
    "start": "5870921127685001066",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "back": "5875082500023258804",
    "door": "5873147866364514353",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "magic": "5474144592817318927",
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

# Ссылка на сайт с правилами (ЗАМЕНИ НА СВОЮ!)
RULES_URL = "https://your-username.github.io/rules/rules.html"

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
                text="✉️ ПОДАТЬ ЗАЯВКУ", 
                callback_data="menu_apply",
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
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

@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = (
        f"{emoji(EMOJI['start'], '🎮')} <b>Добро пожаловать на {SERVER['name']}</b>\n\n"
        f"{emoji(EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{emoji(EMOJI['cat_ok'], '🤙')} <b>Для просмотра информации используйте кнопки ниже</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{emoji(EMOJI['magic'], '✨')} <b>Главное меню</b>\n\nВыберите действие:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{emoji(EMOJI['cat_glasses'], '🔄')} <i>Получаю информацию...</i>",
        parse_mode="HTML"
    )
    
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    
    status = "🟢 РАБОТАЕТ" if java_online > 0 else "🔴 ОФФЛАЙН"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>{SERVER['name']}</b> {status}
{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

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
    
    online = await get_server_online()
    java_online = online.get("java", {}).get("online", 0)
    java_max = online.get("java", {}).get("max", 0)
    
    status = "🟢 РАБОТАЕТ" if java_online > 0 else "🔴 ОФФЛАЙН"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>{SERVER['name']}</b> {status}
{emoji(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
└ Порт: <code>{SERVER['bedrock_port']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['check'], '✅')} Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['door'], '🚪')} <b>ПОЛУЧЕНИЕ ДОСТУПА</b>

{emoji(EMOJI['cat_ok'], '🤙')} <b>Как попасть на сервер:</b>

1️⃣ Напиши заявку: @pelmewki379
2️⃣ Расскажи немного о себе
3️⃣ Дождись ответа администратора

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>Подать заявку:</b> @pelmewki379
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '🐱')}{emoji(EMOJI['anime_dance'], '💃')}{emoji(EMOJI['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

{emoji(EMOJI['crown'], '👑')} <b>Преимущества:</b>
• Эксклюзивные ивенты
• Кастомные эмоции в чате
• Приоритетная поддержка
• Уникальный префикс

{emoji(EMOJI['check'], '✅')} <b>Цена: 299₽ / месяц</b>

{emoji(EMOJI['cat_kiss'], '😘')} <b>Оплата:</b> Карта / СБП / Криптовалюта

{emoji(EMOJI['rabbit_smile'], '🐰')} <i>Для покупки: @pelmewki379</i>
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
    print("🚀 Бот LostEarth запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
