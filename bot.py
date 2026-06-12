import asyncio
import os
import socket
import struct
import json
import re
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
    save_to_log,
    get_balance,
    get_stats,
    update_balance,
    update_stats,
    can_claim_daily_bonus,
    set_daily_bonus_claimed,
    load_players,
    save_players,
    roll_dice_animated
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ДЛЯ WEBAPP ==========
app = Flask(__name__, static_folder='static')

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
    cats = ["cat_dance", "cat_ok", "cat_up", "cat_laugh", "cat_kiss"]
    return premium_emoji(PREMIUM_EMOJI[random.choice(cats)], "🐱")

def random_rabbit():
    return premium_emoji(PREMIUM_EMOJI["rabbit_fly"], "🐰")

def random_heart():
    return premium_emoji(PREMIUM_EMOJI["heart"], "💜")

def random_anime():
    return premium_emoji(PREMIUM_EMOJI["anime_dance"], "💃")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def get_user_bio(user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        return user.bio if user.bio else ""
    except Exception as e:
        print(f"Ошибка получения bio: {e}")
        return ""

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
        [InlineKeyboardButton(text="IP И ОНЛАЙН", callback_data="menu_ip")],
        [InlineKeyboardButton(text="ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL)),
         InlineKeyboardButton(text="ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL))],
        [InlineKeyboardButton(text="ПРЕМИУМ", callback_data="menu_premium"),
         InlineKeyboardButton(text="ЭНДЕРИЯ", callback_data="menu_enderia")]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ОБНОВИТЬ", callback_data="refresh_online")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    online, max_players = await get_server_online()
    
    text = f"""✨ <b>Добро пожаловать на {SERVER['name']}</b>

🏠 <b>{SERVER['mode']}</b>

🐱 <b>Я Эндерия - твой живой помощник!</b>

📊 <b>Текущий онлайн:</b> {online}/{max_players}

💰 <b>Игры с Эндерией:</b>
/bet [сумма] - Ставка на кубик (выигрыш х2)
/balance - Твой баланс
/profile - Твой профиль
/daily - Ежедневный бонус 100💎

✨ <b>Стартовый баланс: 100 алмазов</b>
💎 <b>Минимальная ставка: 10 алмазов</b>

🎁 <b>Как получить бонус?</b>
Добавь в описание профиля: @lostearth_bot

🐰 💃 🐱"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"📊 <b>Онлайн: {online}/{max_players}</b> 🐱", parse_mode="HTML")

@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance(username)
    await message.answer(f"💎 {username}, твой баланс: {balance} алмазов! 🐱", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance(username)
    stats = get_stats(username)
    
    text = f"""👤 <b>ПРОФИЛЬ ИГРОКА</b> 👤

👤 Имя: {username}
💎 Баланс: {balance} алмазов
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
📊 Всего игр: {stats['wins'] + stats['losses']}

🎁 <b>Ежедневный бонус: +100 алмазов</b>
📝 Добавь в описание: @lostearth_bot

🐱 Напиши /daily чтобы получить бонус! 💜"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    from datetime import date
    username = message.from_user.username or message.from_user.first_name
    
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    if not has_bot_in_bio:
        text = f"""❌ <b>НЕТ БОНУСА!</b> ❌

Чтобы получать ежедневный бонус 100 алмазов, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

💜 После добавления напиши /daily снова! 🐱"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if can_claim_daily_bonus(username):
        data = load_players()
        if username not in data:
            data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        data[username]["balance"] = data[username].get("balance", 100) + 100
        data[username]["last_bonus"] = str(date.today())
        save_players(data)
        balance = get_balance(username)
        
        text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> 🎁\n\n✨ +100 алмазов!\n💎 Баланс: {balance} алмазов\n\n🐰 Заходи завтра снова! 💜"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"💜 {username}, ты уже получал бонус сегодня! Возвращайся завтра! 🐱"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("bet"))
async def bet_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    match = re.match(r"^/bet\s+(\d+)$", user_message)
    if not match:
        await message.answer(f"🎲 {username}, используй: /bet [сумма] (например /bet 50)\n💰 Минимальная ставка: 10 алмазов", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    balance = get_balance(username)
    
    if bet_amount < 10:
        await message.answer(f"🎲 {username}, минимальная ставка 10 алмазов! 💎", parse_mode="HTML")
        return
    
    if balance < bet_amount:
        await message.answer(f"💜 {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎", parse_mode="HTML")
        return
    
    await message.answer(f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, message.chat.id)
    
    await asyncio.sleep(1.5)
    await message.answer(f"🐱 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, message.chat.id)
    
    if player_value > bot_value:
        update_balance(username, bet_amount)
        update_stats(username, is_win=True)
        new_balance = get_balance(username)
        await message.answer(
            f"🎉 <b>ПОБЕДА!</b> 🎉\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"✨ Ты выиграл {bet_amount} алмазов!\n"
            f"💎 Баланс: {new_balance} 💜",
            parse_mode="HTML"
        )
    elif player_value < bot_value:
        update_balance(username, -bet_amount)
        update_stats(username, is_win=False)
        new_balance = get_balance(username)
        await message.answer(
            f"😔 <b>ПРОИГРЫШ...</b> 😔\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"💔 Ты проиграл {bet_amount} алмазов!\n"
            f"💎 Баланс: {new_balance} 🐱",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"🤝 <b>НИЧЬЯ!</b> 🤝\n\n"
            f"Оба выбросили {player_value}\n\n"
            f"💰 Ставка возвращена!\n"
            f"💎 Баланс: {balance} 🎲",
            parse_mode="HTML"
        )

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""🎮 <b>ДОСТУПНЫЕ ИГРЫ</b> 🎮

💰 <b>/bet [сумма]</b> - Ставка на кубик (выигрыш х2)
💎 <b>/balance</b> - Показать баланс
👤 <b>/profile</b> - Твой профиль
🎁 <b>/daily</b> - Ежедневный бонус 100💎

✨ <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Твой кубик против кубика Эндерии
• Если твой кубик больше - выигрываешь x2

💎 <b>Стартовый баланс: 100 алмазов</b>

🎁 <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!

🎲 Напиши /bet 50 чтобы сыграть! 🐱"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    await message.answer(f"💜 <b>Статистика диалога с Эндерией:</b>\n\nПросто напиши мне что-нибудь, и я запомню наш разговор! 🐱", parse_mode="HTML")

@dp.message(Command("clear_memory"))
async def clear_memory_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    clear_user_memory(username)
    await message.answer(f"✨ <b>Память очищена!</b>\n\nТеперь мы можем начать новый разговор! 💜", parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""💜 <b>Помощь по боту LostEarth</b>

🔹 <b>Команды сервера:</b>
/start - Главное меню
/online - Показать онлайн

💰 <b>Игры с Эндерией:</b>
/bet [сумма] - Ставка на кубик (выигрыш х2)
/balance - Показать баланс
/profile - Твой профиль
/daily - Ежедневный бонус 100💎

🎁 <b>Как получить бонус?</b>
Добавь в описание профиля: @lostearth_bot

✨ <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Выигрыш: x2 от ставки

🐱 <i>Удачи в игре!</i>"""
    await message.answer(text, parse_mode="HTML")

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    print(f"📥 Получено от {username}: {user_message}")
    save_to_log(username, user_message, is_bot=False)
    
    if user_message.startswith("/"):
        return
    
    # Отвечаем на любое сообщение (убрал проверку should_respond для теста)
    print(f"🎯 Эндерия отвечает {username}")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    response = await get_enderia_response(user_message, username, is_reply=False, chat_id=message.chat.id, bot=bot)
    if response:
        await message.reply(response, parse_mode="HTML")
        print(f"✅ Ответ отправлен {username}")

# ========== КОЛБЭКИ ==========
async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except:
        pass

@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    
    if data == "menu_main":
        online, max_players = await get_server_online()
        text = f"💜 <b>Главное меню</b>\n\n📊 Онлайн: {online}/{max_players}\n\n🐱 Напиши /games чтобы поиграть в кости!"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)
    
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        text = f"👑 <b>LOSTEARTH</b>\n\n💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 <b>Онлайн:</b> {online}/{max_players}\n\n🐰 <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback)
    
    elif data == "refresh_online":
        online_cache.clear()
        last_update.clear()
        online, max_players = await get_server_online()
        text = f"👑 <b>LOSTEARTH</b>\n\n💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 <b>Онлайн:</b> {online}/{max_players}\n\n🐰 <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback, "Онлайн обновлён!")
    
    elif data == "menu_premium":
        text = f"💜 <b>ПРЕМИУМ ДОСТУП</b>\n\n🌿 <b>Друид</b> - 50₽\n🔮 <b>Оракул</b> - 100₽\n👑 <b>Монарх</b> - 200₽\n🪽 <b>Херувим</b> - 300₽ (полёт!)\n🏛️ <b>Архонт</b> - 400₽\n😇 <b>Серафим</b> - 600₽\n\n📩 <b>По вопросам:</b> @pelmewki379\n\n🐱 <i>Хочешь полёт? Бери Херувима!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await safe_callback_answer(callback)
    
    elif data == "menu_enderia":
        text = f"💜 <b>Эндерия - твой живой помощник</b>\n\n🐱 <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n💬 <b>Как ко мне обратиться:</b>\nНапиши: Эндер, Эндерия, Энди\n\n💰 <b>Игры:</b>\n/bet, /balance, /profile, /daily\n\n🎁 <b>Ежедневный бонус 100💎</b>\nДобавь @lostearth_bot в описание профиля!\n\n🐰 <i>Просто позови меня по имени!</i>\n💜"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await safe_callback_answer(callback)

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🤖 Бот: @{bot_info.username}")
    print("💰 Игры: /bet, /balance, /profile, /daily")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
