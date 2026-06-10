# bot.py
import asyncio
import socket
import struct
import json
from datetime import datetime
from typing import Dict
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Информация о сервере
SERVER = {
    "name": "LostEarth",
    "mode": "Мирный режим по заявкам!",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "java_versions": "1.21—1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

# Простые текстовые эмодзи (без кастомных ID)
E = {
    "cat_up": "👍",
    "cat_ok": "🤙",
    "cat_glasses": "😎",
    "rabbit_smile": "🐰",
    "rabbit_fly": "🐰✈️",
    "anime_dance": "💃",
    "cat_kiss": "😘",
    "cat_surprised": "😲",
    "cat_dance": "🐱💃",
    "cat_laugh": "😂",
    "house": "🏠",
    "microphone": "🎤",
    "notification": "🔔",
    "start": "🎮",
    "down": "👇",
    "note": "📝",
    "check": "✅",
    "cross": "❌",
    "analytics": "📊",
    "premium": "💎",
    "crown": "👑",
    "joystick": "🎮",
    "globe": "🌐",
    "back": "◀️",
    "door": "🚪",
}

# Кэш для онлайна
online_cache = {}
last_update = {}

async def get_bedrock_status(ip: str, port: int = 19132, timeout: int = 3):
    """Получение онлайн Bedrock сервера"""
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
            server_name = response[offset:offset+name_length].decode('utf-8', errors='ignore')
            offset += name_length
            
            offset += 4
            offset += response[offset] + 1
            
            online = struct.unpack('<i', response[offset:offset+4])[0]
            offset += 4
            max_players = struct.unpack('<i', response[offset:offset+4])[0]
            
            return {"online": online, "max": max_players, "name": server_name}
    except:
        pass
    return {"online": 0, "max": 0, "name": "Оффлайн"}

async def get_java_status(ip: str, port: int = 25565, timeout: int = 3):
    """Получение онлайн Java сервера"""
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
        
        # send_varint
        value = len(handshake)
        while True:
            if value & ~0x7F == 0:
                sock.send(bytes([value]))
                break
            sock.send(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        
        sock.send(handshake)
        
        # send request
        sock.send(b'\x00\x00')
        
        # read response
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
        return {
            "online": players.get("online", 0),
            "max": players.get("max", 0),
            "version": json_data.get("version", {}).get("name", "?"),
            "motd": json_data.get("description", {}).get("text", "")
        }
    except Exception as e:
        return {"online": 0, "max": 0, "version": "?", "motd": "Оффлайн"}

async def get_server_online():
    now = datetime.now().timestamp()
    
    if "java" in last_update and now - last_update["java"] < 30:
        return online_cache
    
    java_status = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    bedrock_status = await get_bedrock_status(SERVER["bedrock_ip"], SERVER["bedrock_port"])
    
    online_cache["java"] = java_status
    online_cache["bedrock"] = bedrock_status
    last_update["java"] = now
    last_update["bedrock"] = now
    
    return online_cache

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E['door']} IP И ОНЛАЙН", callback_data="menu_ip")],
        [
            InlineKeyboardButton(text=f"{E['note']} ПРАВИЛА", callback_data="menu_rules"),
            InlineKeyboardButton(text=f"{E['rabbit_fly']} ПОДАТЬ ЗАЯВКУ", callback_data="menu_apply")
        ],
        [InlineKeyboardButton(text=f"{E['premium']} ПРЕМИУМ", callback_data="menu_premium")]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E['check']} ОБНОВИТЬ ОНЛАЙН", callback_data="refresh_online")],
        [InlineKeyboardButton(text=f"{E['back']} НАЗАД", callback_data="menu_main")]
    ])

def get_premium_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🐱 КОТИК СТАЙЛ", callback_data="premium_cat"),
            InlineKeyboardButton(text=f"💃 АНИМЕ СТАЙЛ", callback_data="premium_anime")
        ],
        [
            InlineKeyboardButton(text=f"🐰 ЗАЙЧИК СТАЙЛ", callback_data="premium_rabbit"),
            InlineKeyboardButton(text=f"💎 ПРЕМИУМ ВСЁ", callback_data="premium_all")
        ],
        [InlineKeyboardButton(text=f"{E['back']} НАЗАД", callback_data="menu_main")]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        f"🎮 <b>Добро пожаловать на {SERVER['name']}</b> 🎮\n\n"
        f"🏠 <b>{SERVER['mode']}</b>\n\n"
        f"🤙 <i>Выбери действие в меню ниже:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🎮 <b>Главное меню {SERVER['name']}</b> 🎮\n\n"
        f"🏠 <b>{SERVER['mode']}</b>\n\n"
        f"🤙 <i>Выбери действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"😎 <i>Получаю информацию о сервере...</i>",
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
<b>{SERVER['name']}</b> {status}
🏠 <i>{SERVER['mode']}</i>

🎮 <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

🐰✈️ <i>Наслаждайся игрой на LostEarth!</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_ip_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    
    await callback.message.edit_text(
        f"🐱💃 <i>Обновляю онлайн...</i>",
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
<b>{SERVER['name']}</b> {status}
🏠 <i>{SERVER['mode']}</i>

🎮 <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

🐰✈️ <i>Наслаждайся игрой на LostEarth!</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_ip_keyboard()
    )
    await callback.answer(f"👍 Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_rules")
async def menu_rules(callback: CallbackQuery):
    rules_text = f"""
🏠 <b>ПРАВИЛА СЕРВЕРА LOSTEARTH</b> 🏠

😎 <b>Общие правила:</b>
1. 🤝 👍 Уважай других игроков
2. 🚫 ❌ Запрещены читы и баги
3. 💬 🎤 Без токсичности и оскорблений
4. 🏠 🚪 Не гриферь чужие постройки
5. 📝 📝 Администратор всегда прав

🐰 <b>Мирный режим:</b>
• ✅ ПВП только по согласию
• ✅ Территории защищены
• ✅ 🐰✈️ Доступ по заявкам!

💃 <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(
        rules_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E['back']} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    apply_text = f"""
🚪 <b>ПОЛУЧЕНИЕ ДОСТУПА К МИРНОМУ РЕЖИМУ</b> 🚪

🤙 <b>Как попасть на сервер:</b>

1️⃣ 🎮 Напиши заявку в личные сообщения
2️⃣ 📝 Расскажи немного о себе
3️⃣ ✅ Дождись ответа администратора

🐰✈️ <b>Подать заявку:</b> @nikita1055

😘 <i>Добро пожаловать в LostEarth!</i>
"""
    await callback.message.edit_text(
        apply_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E['back']} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💎 <b>ПРЕМИУМ ДОСТУП LOSTEARTH</b> 💎\n\n"
        f"🐱💃 <b>Преимущества:</b>\n"
        f"• 👑 Эксклюзивный доступ к ивентам\n"
        f"• 💃 Кастомные эмоции в чате\n"
        f"• 🐰✈️ Приоритетная поддержка\n"
        f"• 😘 Уникальный префикс в чате\n"
        f"• 🏠 Приватная территория\n\n"
        f"👍 <b>Цена: 299₽ / месяц</b>\n\n"
        f"🐰 <i>Выбери стиль оформления премиума:</i>",
        parse_mode="HTML",
        reply_markup=get_premium_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("premium_"))
async def premium_style(callback: CallbackQuery):
    style = callback.data.split("_")[1]
    styles = {
        "cat": f"🐱💃 КОТИК СТАЙЛ 🐱💃",
        "anime": f"💃 АНИМЕ СТАЙЛ 💃",
        "rabbit": f"🐰✈️ ЗАЙЧИК СТАЙЛ 🐰✈️",
        "all": f"🐱💃💃🐰✈️ ПРЕМИУМ 🐰✈️💃🐱💃"
    }
    
    await callback.message.edit_text(
        f"{styles[style]}\n\n"
        f"😘 <b>Оплата премиум доступа:</b>\n\n"
        f"✅ Карта РФ\n"
        f"✅ СБП\n"
        f"✅ Криптовалюта\n\n"
        f"🤙 <i>Для покупки напиши:</i> @nikita1055\n\n"
        f"🐰 <b>Твой стиль:</b> {styles[style]}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{E['back']} НАЗАД", callback_data="menu_premium")]
        ])
    )
    await callback.answer()

@dp.message(Command("online"))
async def cmd_online(message: Message):
    await message.answer(f"🐱💃 <i>Получаю онлайн...</i>", parse_mode="HTML")
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    await message.answer(
        f"🎮 <b>Онлайн {SERVER['name']}</b>\n\n"
        f"💻 Java: <b>{java.get('online', 0)}/{java.get('max', 0)}</b>\n"
        f"📱 Bedrock: <b>{bedrock.get('online', 0)}/{bedrock.get('max', 0)}</b>",
        parse_mode="HTML"
    )

async def main():
    print("🐱 Бот LostEarth запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
