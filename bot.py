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
    set_server_online,
    add_to_chat_memory,  # ЭТА ФУНКЦИЯ ТЕПЕРЬ БУДЕТ ВЫЗЫВАТЬСЯ ДЛЯ КАЖДОГО СООБЩЕНИЯ
    get_chat_context
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

def random_anime():
    return premium_emoji(PREMIUM_EMOJI["anime_dance"], "💃")

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

# ========== MINECRAFT API ==========
async def get_java_status(ip: str, port: int = 25565):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        
        handshake = bytearray()
        handshake.append(0x00)
        handshake.extend(struct.pack('>i', 0))
        handshake.append(len(ip))
        handshake.extend(ip.encode())
        handshake.extend(struct.pack('>H', port))
        handshake.append(0x01)
        
        sock.send(struct.pack('>i', len(handshake)))
        sock.send(handshake)
        sock.send(b'\x00\x00')
        
        data = sock.recv(1024)
        sock.close()
        
        data_str = data.decode('utf-8', errors='ignore')
        json_start = data_str.find('{')
        if json_start != -1:
            json_end = data_str.rfind('}') + 1
            json_data = json.loads(data_str[json_start:json_end])
            players = json_data.get("players", {})
            return players.get("online", 0), players.get("max", 0)
        return 0, 0
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
    
    set_server_online(online, max_players)
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
    
    text = f"""{random_heart()} <b>Добро пожаловать на {SERVER['name']}</b>

{random_cat()} <b>{SERVER['mode']}</b>

{random_heart()} <b>Я Эндерия - твой живой помощник!</b>

📊 <b>Текущий онлайн:</b> {online}/{max_players}

{random_cat()} <b>Просто напиши моё имя:</b> Энди, Эндерия, Эндер

{random_rabbit()} {random_anime()} {get_enderia_emojis()}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"📊 <b>Онлайн: {online}/{max_players}</b> {random_cat()}", parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    size = get_memory_size(username)
    if size > 0:
        await message.answer(
            f"{random_cat()} <b>{username}, я помню наш диалог!</b>\n\n"
            f"📊 Запомнено сообщений: {size}\n"
            f"{random_heart()} Очистить память: /clear_memory",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{random_heart()} <b>{username}, мы ещё не общались!</b>\n\n"
            f"{random_cat()} Напиши Энди или ответь на моё сообщение",
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
        f"{random_heart()} Теперь можем начать заново!",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""{random_heart()} <b>Помощь по боту LostEarth</b>

🔹 <b>Команды:</b>
/start - Главное меню
/online - Показать онлайн
/stats - Статистика диалога
/clear_memory - Очистить память
/log - Показать лог чата
/help - Справка

{random_cat()} <b>Как общаться:</b>
Напиши: Энди, Эндерия, Эндер

{random_rabbit()} <i>Задавай вопросы!</i>"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("log"))
async def show_log(message: Message):
    """Показать последние сообщения из лога чата"""
    try:
        from enderia import HISTORY_FILE
        import os
        
        if not os.path.exists(HISTORY_FILE):
            await message.answer("❌ Лог файл не найден. Бот ещё не сохранял сообщения.")
            return
        
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            await message.answer("📭 Лог пуст")
            return
        
        # Последние 30 строк
        last_lines = lines[-30:] if len(lines) > 30 else lines
        text = "📜 <b>Последние сообщения в логе чата:</b>\n\n<code>"
        for line in last_lines:
            if len(line) > 200:
                line = line[:200] + "...\n"
            text += line
        text += "</code>"
        
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ========== ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.first_name or "Игрок"
    user_message = message.text
    chat_id = message.chat.id
    chat_title = message.chat.title or "Личка"
    
    # ===== СОХРАНЯЕМ КАЖДОЕ СООБЩЕНИЕ В ЛОГ (ДАЖЕ ЕСЛИ НЕ ОБРАЩАЮТСЯ К ЭНДЕРИИ) =====
    # Добавляем информацию о чате
    log_line = f"[Чат: {chat_title}] {username}: {user_message}"
    add_to_chat_memory(username, user_message, is_bot=False, extra_info=f"[Чат: {chat_title}]")
    
    print(f"📝 [ЛОГ] {chat_title} | {username}: {user_message[:50]}...")
    
    # Проверяем, обращаются ли к Эндерии
    is_mentioned = should_respond(user_message)
    is_reply_to_bot = (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    
    # Отвечаем только если обратились по имени или ответили на сообщение бота
    if is_mentioned or is_reply_to_bot:
        print(f"🎯 Эндерия отвечает {username} (упоминание={is_mentioned}, реплай={is_reply_to_bot})")
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(user_message, username, is_reply=is_reply_to_bot)
        if response:
            await message.reply(response, parse_mode="HTML")
            # Ответ бота тоже сохраняется в add_to_chat_memory внутри get_enderia_response

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
    text = f"""{random_heart()} <b>Главное меню</b>

📊 Онлайн: {online}/{max_players}

{random_cat()} Напиши моё имя или ответь на сообщение"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>

💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>
📊 <b>Онлайн:</b> {online}/{max_players}

{random_rabbit()} <i>Приятной игры!</i>"""
    last_online_data[callback.message.chat.id] = {"online": online, "max": max_players}
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>

💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>
📊 <b>Онлайн:</b> {online}/{max_players}

{random_rabbit()} <i>Приятной игры!</i>"""
    chat_id = callback.message.chat.id
    last_online_data[chat_id] = {"online": online, "max": max_players}
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback, "🔄 Онлайн обновлён!", False)
    except Exception as e:
        if "message is not modified" not in str(e):
            print(f"[ERROR] {e}")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{random_heart()} <b>ПРЕМИУМ ДОСТУП</b>

🌿 <b>Друид</b> - 50₽
🔮 <b>Оракул</b> - 100₽
👑 <b>Монарх</b> - 200₽
🪽 <b>Херувим</b> - 300₽ (полёт!)
🏛️ <b>Архонт</b> - 400₽
😇 <b>Серафим</b> - 600₽

📩 <b>По вопросам:</b> @pelmewki379

{random_cat()} <i>Хочешь полёт? Бери Херувима!</i>"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{random_heart()} <b>Эндерия - твой живой помощник</b>

{random_cat()} <b>Кто я?</b>
Я девушка-эндермен, хранительница Края.

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди

📋 <b>Что я знаю:</b>
• IP и онлайн сервера
• Режимы игры (Мирный и SMP)
• Донаты и цены

📜 <b>Команда /log</b> - показывает историю чата

{random_rabbit()} <i>Просто позови меня по имени!</i>
{random_heart()}"""
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
    print(f"📁 Лог-файл: chat_history/chat.log")
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
