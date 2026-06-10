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

from config import BOT_TOKEN, EMOJI_IDS, emoji, SERVER

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Кэш для онлайна
online_cache = {}
last_update = {}

def e(emoji_id: str, fallback: str = "") -> str:
    """Сокращение для отправки эмодзи"""
    if fallback:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

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
        return {
            "online": players.get("online", 0),
            "max": players.get("max", 0),
            "version": json_data.get("version", {}).get("name", "?"),
        }
    except:
        return {"online": 0, "max": 0, "version": "?"}

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

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{e(EMOJI_IDS['door'], '🚪')} IP И ОНЛАЙН", 
            callback_data="menu_ip"
        )],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['note'], '📜')} ПРАВИЛА", 
                callback_data="menu_rules"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['rabbit_fly'], '🐰')} ПОДАТЬ ЗАЯВКУ", 
                callback_data="menu_apply"
            )
        ],
        [InlineKeyboardButton(
            text=f"{e(EMOJI_IDS['cat_dance'], '🐱')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['rabbit_fly'], '🐰')} ПРЕМИУМ {e(EMOJI_IDS['rabbit_fly'], '🐰')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['cat_dance'], '🐱')}", 
            callback_data="menu_premium"
        )]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{e(EMOJI_IDS['check'], '✅')} ОБНОВИТЬ ОНЛАЙН", 
            callback_data="refresh_online"
        )],
        [InlineKeyboardButton(
            text=f"{e(EMOJI_IDS['back'], '◀️')} НАЗАД", 
            callback_data="menu_main"
        )]
    ])

def get_premium_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['cat_dance'], '🐱')} КОТИК СТАЙЛ", 
                callback_data="premium_cat"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['anime_dance'], '💃')} АНИМЕ СТАЙЛ", 
                callback_data="premium_anime"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['rabbit_fly'], '🐰')} ЗАЙЧИК СТАЙЛ", 
                callback_data="premium_rabbit"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI_IDS['cat_dance'], '🐱')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['rabbit_fly'], '🐰')} ПРЕМИУМ", 
                callback_data="premium_all"
            )
        ],
        [InlineKeyboardButton(
            text=f"{e(EMOJI_IDS['back'], '◀️')} НАЗАД", 
            callback_data="menu_main"
        )]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        f"{e(EMOJI_IDS['start'], '🎮')} <b>Добро пожаловать на {SERVER['name']}</b> {e(EMOJI_IDS['start'], '🎮')}\n\n"
        f"{e(EMOJI_IDS['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{e(EMOJI_IDS['cat_ok'], '🤙')} <i>Выбери действие в меню ниже:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI_IDS['start'], '🎮')} <b>Главное меню {SERVER['name']}</b> {e(EMOJI_IDS['start'], '🎮')}\n\n"
        f"{e(EMOJI_IDS['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{e(EMOJI_IDS['cat_ok'], '🤙')} <i>Выбери действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI_IDS['cat_glasses'], '😎')} <i>Получаю информацию о сервере...</i>",
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
{e(EMOJI_IDS['house'], '🏠')} <i>{SERVER['mode']}</i>

{e(EMOJI_IDS['joystick'], '🎮')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{e(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Наслаждайся игрой на LostEarth!</i>
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
        f"{e(EMOJI_IDS['cat_dance'], '🐱')} <i>Обновляю онлайн...</i>",
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
{e(EMOJI_IDS['house'], '🏠')} <i>{SERVER['mode']}</i>

{e(EMOJI_IDS['joystick'], '🎮')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{e(EMOJI_IDS['rabbit_fly'], '🐰')} <i>Наслаждайся игрой на LostEarth!</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_ip_keyboard()
    )
    await callback.answer(f"{e(EMOJI_IDS['cat_up'], '✅')} Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_rules")
async def menu_rules(callback: CallbackQuery):
    rules_text = f"""
{e(EMOJI_IDS['house'], '🏠')} <b>ПРАВИЛА СЕРВЕРА LOSTEARTH</b> {e(EMOJI_IDS['house'], '🏠')}

{e(EMOJI_IDS['cat_glasses'], '😎')} <b>Общие правила:</b>
1. 🤝 {e(EMOJI_IDS['cat_up'], '👍')} Уважай других игроков
2. 🚫 {e(EMOJI_IDS['cross'], '❌')} Запрещены читы и баги
3. 💬 {e(EMOJI_IDS['microphone'], '🎤')} Без токсичности и оскорблений
4. 🏠 {e(EMOJI_IDS['door'], '🚪')} Не гриферь чужие постройки
5. 📝 {e(EMOJI_IDS['note'], '📝')} Администратор всегда прав

{e(EMOJI_IDS['rabbit_smile'], '🐰')} <b>Мирный режим:</b>
• {e(EMOJI_IDS['check'], '✅')} ПВП только по согласию
• {e(EMOJI_IDS['check'], '✅')} Территории защищены
• {e(EMOJI_IDS['check'], '✅')} {e(EMOJI_IDS['rabbit_fly'], '🐰')} Доступ по заявкам!

{e(EMOJI_IDS['anime_dance'], '💃')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(
        rules_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI_IDS['back'], '◀️')} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    apply_text = f"""
{e(EMOJI_IDS['door'], '🚪')} <b>ПОЛУЧЕНИЕ ДОСТУПА К МИРНОМУ РЕЖИМУ</b> {e(EMOJI_IDS['door'], '🚪')}

{e(EMOJI_IDS['cat_ok'], '🤙')} <b>Как попасть на сервер:</b>

1️⃣ {e(EMOJI_IDS['start'], '🎮')} Напиши заявку в личные сообщения
2️⃣ {e(EMOJI_IDS['note'], '📝')} Расскажи немного о себе
3️⃣ {e(EMOJI_IDS['check'], '✅')} Дождись ответа администратора

{e(EMOJI_IDS['rabbit_fly'], '🐰')} <b>Подать заявку:</b> @nikita1055

{e(EMOJI_IDS['cat_kiss'], '😘')} <i>Добро пожаловать в LostEarth!</i>
"""
    await callback.message.edit_text(
        apply_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI_IDS['back'], '◀️')} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI_IDS['cat_dance'], '🐱')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП LOSTEARTH</b> {e(EMOJI_IDS['rabbit_fly'], '🐰')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['cat_dance'], '🐱')}\n\n"
        f"{e(EMOJI_IDS['cat_dance'], '🐱')} <b>Преимущества:</b>\n"
        f"• {e(EMOJI_IDS['crown'], '👑')} Эксклюзивный доступ к ивентам\n"
        f"• {e(EMOJI_IDS['anime_dance'], '💃')} Кастомные эмоции в чате\n"
        f"• {e(EMOJI_IDS['rabbit_fly'], '🐰')} Приоритетная поддержка\n"
        f"• {e(EMOJI_IDS['cat_kiss'], '😘')} Уникальный префикс в чате\n"
        f"• {e(EMOJI_IDS['house'], '🏠')} Приватная территория\n\n"
        f"{e(EMOJI_IDS['cat_up'], '👍')} <b>Цена: 299₽ / месяц</b>\n\n"
        f"{e(EMOJI_IDS['rabbit_smile'], '🐰')} <i>Выбери стиль оформления премиума:</i>",
        parse_mode="HTML",
        reply_markup=get_premium_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("premium_"))
async def premium_style(callback: CallbackQuery):
    style = callback.data.split("_")[1]
    styles = {
        "cat": f"{e(EMOJI_IDS['cat_dance'], '🐱')} КОТИК СТАЙЛ {e(EMOJI_IDS['cat_dance'], '🐱')}",
        "anime": f"{e(EMOJI_IDS['anime_dance'], '💃')} АНИМЕ СТАЙЛ {e(EMOJI_IDS['anime_dance'], '💃')}",
        "rabbit": f"{e(EMOJI_IDS['rabbit_fly'], '🐰')} ЗАЙЧИК СТАЙЛ {e(EMOJI_IDS['rabbit_fly'], '🐰')}",
        "all": f"{e(EMOJI_IDS['cat_dance'], '🐱')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['rabbit_fly'], '🐰')} ПРЕМИУМ ВСЁ {e(EMOJI_IDS['rabbit_fly'], '🐰')}{e(EMOJI_IDS['anime_dance'], '💃')}{e(EMOJI_IDS['cat_dance'], '🐱')}"
    }
    
    await callback.message.edit_text(
        f"{styles[style]}\n\n"
        f"{e(EMOJI_IDS['cat_kiss'], '😘')} <b>Оплата премиум доступа:</b>\n\n"
        f"{e(EMOJI_IDS['check'], '✅')} Карта РФ\n"
        f"{e(EMOJI_IDS['check'], '✅')} СБП\n"
        f"{e(EMOJI_IDS['check'], '✅')} Криптовалюта\n\n"
        f"{e(EMOJI_IDS['cat_ok'], '🤙')} <i>Для покупки напиши:</i> @nikita1055\n\n"
        f"{e(EMOJI_IDS['rabbit_smile'], '🐰')} <b>Твой стиль:</b> {styles[style]}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI_IDS['back'], '◀️')} НАЗАД", callback_data="menu_premium")]
        ])
    )
    await callback.answer()

@dp.message(Command("online"))
async def cmd_online(message: Message):
    await message.answer(f"{e(EMOJI_IDS['cat_dance'], '🐱')} <i>Получаю онлайн...</i>", parse_mode="HTML")
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    await message.answer(
        f"{e(EMOJI_IDS['joystick'], '🎮')} <b>Онлайн {SERVER['name']}</b>\n\n"
        f"💻 Java: <b>{java.get('online', 0)}/{java.get('max', 0)}</b>\n"
        f"📱 Bedrock: <b>{bedrock.get('online', 0)}/{bedrock.get('max', 0)}</b>",
        parse_mode="HTML"
    )

async def main():
    print("🐱 Бот LostEarth запущен!")
    print(f"Используются эмодзи: котик танцует={EMOJI_IDS['cat_dance']}, аниме={EMOJI_IDS['anime_dance']}, зайчик={EMOJI_IDS['rabbit_fly']}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
