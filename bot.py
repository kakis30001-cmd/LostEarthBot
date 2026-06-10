import asyncio
import socket
import struct
import json
from datetime import datetime
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, EMOJI, emoji, SERVER

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Кэш для онлайна
online_cache = {}
last_update = {}

async def get_bedrock_status(ip: str, port: int = 19132, timeout: int = 3):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        ping_data = bytearray(b'\x01')
        ping_data += b'\x00' * 15
        ping_data += struct.pack('<Q', 0)
        ping_data += struct.pack('<Q', 0)
        writer.write(ping_data)
        await writer.drain()
        response = await asyncio.wait_for(reader.read(2048), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        if len(response) > 35:
            offset = 35
            name_length = response[offset]
            offset += 1
            offset += name_length
            offset += 4
            offset += response[offset] + 1
            online = struct.unpack('<i', response[offset:offset+4])[0]
            offset += 4
            max_players = struct.unpack('<i', response[offset:offset+4])[0]
            return {"online": online, "max": max_players}
    except:
        pass
    return {"online": 0, "max": 0}

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
    bedrock_status = await get_bedrock_status(SERVER["bedrock_ip"], SERVER["bedrock_port"])
    online_cache["java"] = java_status
    online_cache["bedrock"] = bedrock_status
    last_update["java"] = now
    return online_cache

# ========== КНОПКИ КАК В ТВОЁМ ПРИМЕРЕ ==========

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
                callback_data="menu_rules",
                icon_custom_emoji_id=EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="ПОДАТЬ ЗАЯВКУ", 
                callback_data="menu_apply",
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
                text="ОБНОВИТЬ ОНЛАЙН", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["arrow_back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========

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
        f"{emoji(EMOJI['cat_glasses'], '🔄')} <i>Получаю информацию о сервере...</i>",
        parse_mode="HTML"
    )
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    java_online = java.get("online", 0)
    java_max = java.get("max", 0)
    bedrock_online = bedrock.get("online", 0)
    bedrock_max = bedrock.get("max", 0)
    
    status = "🟢 РАБОТАЕТ" if java_online > 0 or bedrock_online > 0 else "🔴 ОФФЛАЙН"
    
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
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Наслаждайся игрой на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    java_online = java.get("online", 0)
    java_max = java.get("max", 0)
    bedrock_online = bedrock.get("online", 0)
    bedrock_max = bedrock.get("max", 0)
    
    status = "🟢 РАБОТАЕТ" if java_online > 0 or bedrock_online > 0 else "🔴 ОФФЛАЙН"
    
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
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Наслаждайся игрой на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['cat_up'], '✅')} Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_rules")
async def menu_rules(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['house'], '🏠')} <b>ПРАВИЛА СЕРВЕРА LOSTEARTH</b>

{emoji(EMOJI['cat_glasses'], '😎')} <b>Общие правила:</b>
• {emoji(EMOJI['cat_up'], '👍')} Уважайте других игроков
• {emoji(EMOJI['cross'], '❌')} Запрещены читы и баги
• {emoji(EMOJI['microphone'], '🎤')} Без токсичности и оскорблений
• {emoji(EMOJI['door'], '🚪')} Не гриферь чужие постройки

{emoji(EMOJI['rabbit_smile'], '🐰')} <b>Мирный режим:</b>
• {emoji(EMOJI['check'], '✅')} ПВП только по согласию
• {emoji(EMOJI['check'], '✅')} Территории защищены
• {emoji(EMOJI['check'], '✅')} Доступ по заявкам!

{emoji(EMOJI['anime_dance'], '💃')} <i>Приятной игры!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["arrow_back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['door'], '🚪')} <b>ПОЛУЧЕНИЕ ДОСТУПА</b>

{emoji(EMOJI['cat_ok'], '🤙')} <b>Как попасть на сервер:</b>

1️⃣ Напиши заявку: @nikita1055
2️⃣ Расскажи немного о себе
3️⃣ Дождись ответа администратора

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>Подать заявку:</b> @nikita1055
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["arrow_back"])]
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

{emoji(EMOJI['cat_up'], '👍')} <b>Цена: 299₽ / месяц</b>

{emoji(EMOJI['cat_kiss'], '😘')} <b>Оплата:</b> Карта РФ / СБП / Криптовалюта

{emoji(EMOJI['rabbit_smile'], '🐰')} <i>Для покупки: @nikita1055</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["arrow_back"])]
        ])
    )
    await callback.answer()

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн {SERVER['name']}</b>\n\n"
        f"💻 Java: {java.get('online', 0)}/{java.get('max', 0)}\n"
        f"📱 Bedrock: {bedrock.get('online', 0)}/{bedrock.get('max', 0)}",
        parse_mode="HTML"
    )

async def main():
    print("🚀 Бот LostEarth запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
