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

from config import BOT_TOKEN, EMOJI, emoji, SERVERS, RULES_PEACEFUL, RULES_SMP, DONATES

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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

async def get_server_online(mode: str):
    now = datetime.now().timestamp()
    cache_key = f"{mode}_java"
    
    if cache_key in last_update and now - last_update[cache_key] < 30:
        return online_cache.get(cache_key, {"online": 0, "max": 0})
    
    server = SERVERS[mode]
    status = await get_java_status(server["java_ip"], server["java_port"])
    online_cache[cache_key] = status
    last_update[cache_key] = now
    return status

# ========== КЛАВИАТУРЫ ==========

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['house'], '🌾')} МИРНЫЙ РЕЖИМ",
                callback_data="mode_peaceful",
                icon_custom_emoji_id=EMOJI["cat_rose"]
            ),
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['crown'], '⚔️')} SMP РЕЖИМ",
                callback_data="mode_smp",
                icon_custom_emoji_id=EMOJI["cat_money"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['note'], '📜')} ПРАВИЛА",
                callback_data="menu_rules",
                icon_custom_emoji_id=EMOJI["cat_glasses"]
            ),
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['rabbit_fly'], '🎁')} ДОНАТ",
                callback_data="menu_donate",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            )
        ]
    ])

def get_rules_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['house'], '🌾')} ПРАВИЛА МИРНОГО",
                callback_data="rules_peaceful",
                icon_custom_emoji_id=EMOJI["cat_glasses"]
            ),
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['crown'], '⚔️')} ПРАВИЛА SMP",
                callback_data="rules_smp",
                icon_custom_emoji_id=EMOJI["cat_angry"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД",
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

def get_donate_keyboard():
    buttons = []
    for key, donate in DONATES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{donate['emoji']} {donate['name']} | {donate['price_rub']}₽ / {donate['price_hrn']}₴",
                callback_data=f"donate_{key}",
                icon_custom_emoji_id=EMOJI["cat_money"]
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД",
            callback_data="menu_main",
            icon_custom_emoji_id=EMOJI["back"]
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_mode_keyboard(mode: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['check'], '🔄')} ОБНОВИТЬ ОНЛАЙН",
                callback_data=f"refresh_{mode}",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД",
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========

@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = f"""
{emoji(EMOJI['cat_rose'], '🌸')} <b>Добро пожаловать на LostEarth!</b> {emoji(EMOJI['cat_rose'], '🌸')}

{emoji(EMOJI['cat_ok'], '🐱')} <i>Выбери режим игры:</i>
    """
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{emoji(EMOJI['cat_think'], '🤔')} <b>Главное меню</b>\n\nВыберите действие:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def show_mode(callback: CallbackQuery):
    mode = callback.data.split("_")[1]
    server = SERVERS[mode]
    online = await get_server_online(mode)
    
    status_emoji = emoji(EMOJI["cat_up"], "🟢") if online["online"] > 0 else emoji(EMOJI["cat_surprised"], "🔴")
    status_text = "РАБОТАЕТ" if online["online"] > 0 else "ОФФЛАЙН"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>{server['name']}</b> {status_emoji} {status_text}

{server['description']}

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{server['java_ip']}</code>
├ Порт: <code>{server['java_port']}</code>
├ Версия: <code>{server['version']}</code>
└ Онлайн: <b>{online['online']}/{online['max']}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{server['bedrock_ip']}</code>
├ Порт: <code>{server['bedrock_port']}</code>
└ Версия: <code>{server['version']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_mode_keyboard(mode))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("refresh_"))
async def refresh_online(callback: CallbackQuery):
    mode = callback.data.split("_")[1]
    
    # очищаем кэш
    cache_key = f"{mode}_java"
    if cache_key in online_cache:
        del online_cache[cache_key]
    if cache_key in last_update:
        del last_update[cache_key]
    
    server = SERVERS[mode]
    online = await get_server_online(mode)
    
    status_emoji = emoji(EMOJI["cat_up"], "🟢") if online["online"] > 0 else emoji(EMOJI["cat_surprised"], "🔴")
    status_text = "РАБОТАЕТ" if online["online"] > 0 else "ОФФЛАЙН"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>{server['name']}</b> {status_emoji} {status_text}

{server['description']}

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{server['java_ip']}</code>
├ Порт: <code>{server['java_port']}</code>
├ Версия: <code>{server['version']}</code>
└ Онлайн: <b>{online['online']}/{online['max']}</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{server['bedrock_ip']}</code>
├ Порт: <code>{server['bedrock_port']}</code>
└ Версия: <code>{server['version']}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_mode_keyboard(mode))
    await callback.answer(f"{emoji(EMOJI['cat_up'], '✅')} Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_rules")
async def menu_rules(callback: CallbackQuery):
    text = f"{emoji(EMOJI['cat_glasses'], '📜')} <b>Выбери режим для просмотра правил:</b>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_rules_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "rules_peaceful")
async def rules_peaceful(callback: CallbackQuery):
    await callback.message.edit_text(
        RULES_PEACEFUL,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД", callback_data="menu_rules", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "rules_smp")
async def rules_smp(callback: CallbackQuery):
    await callback.message.edit_text(
        RULES_SMP,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД", callback_data="menu_rules", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_donate")
async def menu_donate(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_money'], '💰')} <b>ДОНАТЫ МИРНОГО РЕЖИМА</b> {emoji(EMOJI['cat_money'], '💰')}

{emoji(EMOJI['rabbit_tongue'], '👅')} <i>Принимаю любую валютой!</i>
{emoji(EMOJI['cat_kiss'], '💝')} <i>Для уточнения писать в ЛС:</i> @pelmewki379

{emoji(EMOJI['cat_think'], '🤔')} <b>Выбери донат:</b>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_donate_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("donate_"))
async def show_donate(callback: CallbackQuery):
    donate_key = callback.data.split("_")[1]
    donate = DONATES[donate_key]
    
    features_text = "\n".join([f"• {f}" for f in donate["features"]])
    
    text = f"""
{emoji(EMOJI['cat_dance'], '✨')} <b>{donate['name']}</b> {donate['emoji']}

{emoji(EMOJI['cat_money'], '💰')} <b>Цена:</b>
├ {donate['price_hrn']} ₴ (гривны)
└ {donate['price_rub']} ₽ (рубли)

{emoji(EMOJI['cat_rose'], '🌹')} <b>Возможности:</b>
{features_text}

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>Как приобрести:</b>
Напиши @pelmewki379

{emoji(EMOJI['cat_kiss'], '😘')} <i>Спасибо за поддержку сервера!</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{emoji(EMOJI['back'], '◀️')} НАЗАД К ДОНАТАМ", callback_data="menu_donate", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.message(Command("online"))
async def cmd_online(message: Message):
    text = f"{emoji(EMOJI['cat_dance'], '🔄')} <i>Получаю онлайн...</i>"
    await message.answer(text, parse_mode="HTML")
    
    for mode in ["peaceful", "smp"]:
        server = SERVERS[mode]
        online = await get_server_online(mode)
        status = "🟢" if online["online"] > 0 else "🔴"
        await message.answer(f"{status} {server['name']}: {online['online']}/{online['max']}")

async def main():
    print("🐱 Бот LostEarth запущен!")
    print(f"Котики, зайцы и аниме в деле! 🎉")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
