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

from enderia import (
    get_enderia_response, 
    should_respond, 
    clear_user_memory, 
    get_memory_size, 
    set_server_online
)
from prompts import get_enderia_emojis

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ДЛЯ WEBAPP ==========
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
    "cat_money": "5267058870580191916",
    "cat_laugh": "5276391181679366784",
    "anime_dance": "6325682031741109665",
}

def premium_emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def random_cat():
    cats = [PREMIUM_EMOJI["cat_dance"], PREMIUM_EMOJI["cat_ok"], PREMIUM_EMOJI["cat_up"], PREMIUM_EMOJI["cat_laugh"]]
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
    "java_versions": "1.21 — 1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

BASE_URL = os.getenv("BASE_URL", "https://lostearthbot-production.up.railway.app")
RULES_URL = f"{BASE_URL}/rules.html"
APPLY_URL = f"{BASE_URL}/apply.html"

online_cache = {}
last_update = {}
last_online_data = {}

# ========== MINECRAFT API (ИСПРАВЛЕННЫЙ) ==========
async def get_java_status(ip: str, port: int = 25565):
    """Получает статус Java сервера через Server List Ping (SLP) протокол"""
    try:
        # Создаём сокет с таймаутом
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # Увеличен таймаут до 5 секунд
        
        # Подключаемся
        sock.connect((ip, port))
        
        # Формируем handshake пакет (протокол 754 = 1.21+)
        # packet ID 0x00 (Handshake)
        handshake = bytearray()
        handshake.append(0x00)  # Packet ID
        
        # Protocol version (754 = 1.21, 767 = 1.21.1, 770 = 1.21.3)
        # Используем 754 как базовый
        protocol = 754
        handshake.extend(struct.pack('>i', protocol))  # VarInt как int
        
        # Server address
        host_bytes = ip.encode('utf-8')
        handshake.append(len(host_bytes))
        handshake.extend(host_bytes)
        
        # Server port
        handshake.extend(struct.pack('>H', port))
        
        # Next state: 1 for status
        handshake.append(0x01)
        
        # Отправляем handshake с правильным префиксом длины
        packet_length = len(handshake)
        sock.send(struct.pack('>i', packet_length))  # Длина пакета как int
        sock.send(handshake)
        
        # Отправляем запрос статуса (packet ID 0x00)
        sock.send(b'\x00\x00')  # Длина 0, packet ID 0
        
        # Читаем длину ответа
        data = sock.recv(1024)
        if not data:
            sock.close()
            return 0, 0
        
        # Распарсить VarInt длину
        data = data[1:]  # Пропускаем первый байт (длина пакета)
        
        # Ищем начало JSON
        json_start = data.find(b'{')
        if json_start == -1:
            sock.close()
            return 0, 0
        
        json_data = data[json_start:].decode('utf-8', errors='ignore')
        players = json.loads(json_data).get("players", {})
        
        sock.close()
        
        online = players.get("online", 0)
        max_players = players.get("max", 0)
        
        print(f"📊 Статус сервера {ip}:{port} - Онлайн: {online}/{max_players}")
        return online, max_players
        
    except socket.timeout:
        print(f"⏰ Таймаут подключения к {ip}:{port}")
        return 0, 0
    except ConnectionRefusedError:
        print(f"🔌 Отказ соединения {ip}:{port} - сервер не запущен")
        return 0, 0
    except Exception as e:
        print(f"❌ Ошибка получения статуса {ip}:{port}: {e}")
        return 0, 0

async def get_bedrock_status(ip: str, port: int = 19132):
    """Получает статус Bedrock сервера (простой ping)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        
        # Bedrock ping запрос (Unconnected Ping)
        # 0x01 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 + random 8 bytes
        ping_data = bytearray([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Добавляем случайные байты
        for _ in range(8):
            ping_data.append(random.randint(0, 255))
        
        sock.sendto(ping_data, (ip, port))
        
        try:
            data, addr = sock.recvfrom(2048)
            sock.close()
            # Если получили ответ - сервер работает
            # Для Bedrock сложно получить точный онлайн без полного парсинга
            return 1, 100  # Возвращаем 1 как индикатор что сервер жив
        except:
            sock.close()
            return 0, 0
    except Exception as e:
        print(f"❌ Bedrock ошибка: {e}")
        return 0, 0

async def get_server_online():
    """Возвращает онлайн сервера (с кэшированием)"""
    now = datetime.now().timestamp()
    
    # Кэш на 30 секунд
    if "online" in last_update and now - last_update["online"] < 30:
        cached_online = online_cache.get("online", 0)
        cached_max = online_cache.get("max", 0)
        print(f"📦 Кэш: онлайн {cached_online}/{cached_max}")
        return cached_online, cached_max
    
    print("🔄 Обновление статуса сервера...")
    
    # Пробуем получить статус
    online, max_players = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    
    # Если не удалось получить онлайн - проверяем Bedrock как запасной вариант
    if online == 0:
        bedrock_online, _ = await get_bedrock_status(SERVER["bedrock_ip"], SERVER["bedrock_port"])
        if bedrock_online > 0:
            # Сервер жив, но Java статус не получен
            online = 1  # Хотя бы показываем что сервер онлайн
            max_players = 100  # Примерное значение
    
    # Сохраняем в кэш
    online_cache["online"] = online
    online_cache["max"] = max_players
    last_update["online"] = now
    
    # Обновляем для Эндерии
    set_server_online(online, max_players)
    
    print(f"📊 Итоговый онлайн: {online}/{max_players}")
    return online, max_players

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="IP И ОНЛАЙН", callback_data="menu_ip", icon_custom_emoji_id=PREMIUM_EMOJI["door"])],
        [InlineKeyboardButton(text="ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL), icon_custom_emoji_id=PREMIUM_EMOJI["note"]),
         InlineKeyboardButton(text="ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL), icon_custom_emoji_id=PREMIUM_EMOJI["rabbit_fly"])],
        [InlineKeyboardButton(text="ПРЕМИУМ", callback_data="menu_premium", icon_custom_emoji_id=PREMIUM_EMOJI["cat_dance"]),
         InlineKeyboardButton(text="ЭНДЕРИЯ", callback_data="menu_enderia", icon_custom_emoji_id=PREMIUM_EMOJI["cat_ok"])]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ОБНОВИТЬ", callback_data="refresh_online", icon_custom_emoji_id=PREMIUM_EMOJI["check"])],
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=PREMIUM_EMOJI["back"])]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=PREMIUM_EMOJI["back"])]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    online, max_players = await get_server_online()
    
    text = f"""{premium_emoji(PREMIUM_EMOJI['start'], '✨')} <b>Добро пожаловать на {SERVER['name']}</b>

{premium_emoji(PREMIUM_EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>

{random_cat()} <b>Я Эндерия - твой живой помощник!</b>

📊 <b>Текущий онлайн:</b> {online}/{max_players}

🐱 <b>Просто напиши моё имя или ответь на моё сообщение!</b>

{get_enderia_emojis()}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"📊 <b>Онлайн: {online}/{max_players}</b>", parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    size = get_memory_size(username)
    if size > 0:
        await message.answer(f"{random_cat()} <b>{username}, я помню наш диалог!</b>\n\n📊 Запомнено сообщений: {size}\n✨ Очистить память: /clear_memory", parse_mode="HTML")
    else:
        await message.answer(f"{random_heart()} <b>{username}, мы ещё не общались!</b>\n\n📝 Напиши Энди или ответь на моё сообщение", parse_mode="HTML")

@dp.message(Command("clear_memory"))
async def clear_memory_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    old_size = get_memory_size(username)
    clear_user_memory(username)
    await message.answer(f"{random_cat()} ✨ <b>Память очищена!</b>\n\n📊 Было запомнено: {old_size} сообщений", parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""{random_heart()} <b>Помощь по боту LostEarth</b>

<b>🔹 Команды:</b>
/start - Главное меню
/online - Показать онлайн
/stats - Статистика диалога
/clear_memory - Очистить память
/help - Справка

<b>🔹 Как общаться:</b>
Напиши: Энди, Эндерия, Эндер
Или просто ответь на моё сообщение

{random_cat()} <i>Задавай вопросы!</i>"""
    await message.answer(text, parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.first_name or "Игрок"
    user_message = message.text
    
    is_mentioned = should_respond(user_message)
    is_reply_to_bot = (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    
    if is_mentioned or is_reply_to_bot:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(user_message, username, is_reply=is_reply_to_bot)
        if response:
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        if "query is too old" not in str(e):
            print(f"[ERROR] {e}")

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""✨ <b>Главное меню</b>\n\n📊 Онлайн: {online}/{max_players}\n\n🐱 Напиши моё имя или ответь на сообщение"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>\n\n💻 Java: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 Bedrock: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 Онлайн: {online}/{max_players}\n\n🐰 Приятной игры!"""
    last_online_data[callback.message.chat.id] = {"online": online, "max": max_players}
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    # Принудительно очищаем кэш
    last_update.clear()
    online_cache.clear()
    
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>\n\n💻 Java: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 Bedrock: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 Онлайн: {online}/{max_players}\n\n🐰 Приятной игры!"""
    chat_id = callback.message.chat.id
    last_data = last_online_data.get(chat_id, {})
    if last_data.get("online") == online and last_data.get("max") == max_players:
        await safe_callback_answer(callback, "✨ Онлайн не изменился!", False)
        return
    last_online_data[chat_id] = {"online": online, "max": max_players}
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback, "🔄 Онлайн обновлён!", False)
    except Exception as e:
        if "message is not modified" in str(e):
            await safe_callback_answer(callback, "✨ Онлайн не изменился!", False)

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""💎 <b>ПРЕМИУМ ДОСТУП</b>\n\n🌿 Друид - 50₽\n🔮 Оракул - 100₽\n👑 Монарх - 200₽\n🪽 Херувим - 300₽\n🏛️ Архонт - 400₽\n😇 Серафим - 600₽\n\n📩 @pelmewki379"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{random_heart()} <b>Эндерия</b>\n\n{random_cat()} Я девушка-эндермен из LostEarth!\n\n💬 Напиши: Эндер, Эндерия, Энди\n\n{random_rabbit()} Позови меня!"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🎨 Премиум эмодзи загружено: {len(PREMIUM_EMOJI)}")
    print(f"🤖 Бот: @{bot_info.username}")
    print("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        if "Conflict" in str(e):
            print("⚠️ Конфликт, перезапуск через 5 секунд...")
            await asyncio.sleep(5)
            await dp.start_polling(bot)
        else:
            raise e

if __name__ == "__main__":
    asyncio.run(main())
