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
    get_xp,
    update_xp,
    get_stats,
    update_stats,
    get_farms,
    buy_farm,
    upgrade_farm,
    claim_income,
    calculate_income,
    get_leaderboard,
    can_claim_daily_bonus,
    claim_daily_bonus,
    set_server_online,
    save_to_log,
    roll_dice_animated,
    init_player,
    last_active,
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ==========
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

# ========== КОНФИГ ==========
SERVER = {
    "name": "LostEarth",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
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

async def get_user_bio(user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        return user.bio if user.bio else ""
    except:
        return ""

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥️ IP И ОНЛАЙН", callback_data="menu_ip")],
        [InlineKeyboardButton(text="📜 ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL)),
         InlineKeyboardButton(text="📝 ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL))],
        [InlineKeyboardButton(text="👑 ПРЕМИУМ", callback_data="menu_premium"),
         InlineKeyboardButton(text="💜 ЭНДЕРИЯ", callback_data="menu_enderia")],
        [InlineKeyboardButton(text="🏭 ФЕРМЫ", callback_data="menu_farms"),
         InlineKeyboardButton(text="🏆 ТОП", callback_data="menu_top")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

# ========== КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    init_player(username)
    online, max_players = await get_server_online()
    
    text = f"""✨ <b>Добро пожаловать на {SERVER['name']}</b> ✨

🏠 <b>Мирный режим по заявкам!</b>

🐱 <b>Я Эндерия - твой живой помощник!</b>

📊 <b>Текущий онлайн:</b> {online}/{max_players}

💰 <b>ИГРЫ:</b>
🎲 /bet [сумма] - игра в кости (x2)
👑 /balance - баланс опыта
👤 /profile - твой профиль
🎁 /daily - бонус 500 XP

🏭 <b>ФЕРМЫ ОПЫТА:</b>
📋 /farms - твои фермы
💰 /buy_farm - купить ферму
⬆️ /upgrade_farm - улучшить ферму
📦 /claim - собрать опыт
🏆 /leaderboard - топ игроков

💎 <b>Стартовый баланс: 1000 XP</b>
🎲 <b>Минимальная ставка: 50 XP</b>

🎁 <b>Как получить бонус?</b>
Добавь @lostearth_bot в описание профиля!

🐰💜🐱"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"📊 <b>Онлайн: {online}/{max_players}</b> 🐱", parse_mode="HTML")

@dp.message(Command("balance"))
@dp.message(Command("bal"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    await message.answer(f"💰 {username}, твой баланс: {xp} XP! 🎮", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    stats = get_stats(username)
    farms = get_farms(username)
    farm_count = len(farms)
    total_income = calculate_income(farms)
    
    text = f"""📊 <b>ПРОФИЛЬ ИГРОКА</b> 📊

👤 Имя: {username}
💎 Опыт: {xp} XP
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
🏭 Ферм: {farm_count}
📈 Доход в час: {total_income} XP

🎁 <b>Ежедневный бонус: +500 XP</b>
📝 Добавь в описание: @lostearth_bot

🐱 /daily - получить бонус! 💜"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    if not has_bot_in_bio:
        text = f"""❌ <b>НЕТ БОНУСА!</b> ❌

Чтобы получать ежедневный бонус 500 XP, добавь в описание своего профиля:

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
        amount = claim_daily_bonus(username)
        xp = get_xp(username)
        text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> 🎁\n\n✨ +{amount} XP!\n💰 Баланс: {xp} XP\n\n🐰 Заходи завтра снова! 💜"
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
        await message.answer(f"🎲 {username}, используй: /bet [сумма]\n💰 Минимальная ставка: 50 XP\n💰 Пример: /bet 100", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    xp = get_xp(username)
    
    if bet_amount < 50:
        await message.answer(f"🎲 {username}, минимальная ставка 50 XP!", parse_mode="HTML")
        return
    
    if xp < bet_amount:
        await message.answer(f"💜 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount}", parse_mode="HTML")
        return
    
    await message.answer(f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, message.chat.id)
    
    await asyncio.sleep(1.5)
    await message.answer(f"🐱 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, message.chat.id)
    
    if player_value > bot_value:
        update_xp(username, bet_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        await message.answer(
            f"🎉 <b>ПОБЕДА!</b> 🎉\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"✨ Ты выиграл {bet_amount} XP!\n"
            f"💰 Баланс: {new_xp} XP 💜",
            parse_mode="HTML"
        )
    elif player_value < bot_value:
        update_xp(username, -bet_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        await message.answer(
            f"😔 <b>ПРОИГРЫШ...</b> 😔\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"💔 Ты проиграл {bet_amount} XP!\n"
            f"💰 Баланс: {new_xp} XP 🐱",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"🤝 <b>НИЧЬЯ!</b> 🤝\n\n"
            f"Оба выбросили {player_value}\n\n"
            f"💰 Ставка возвращена!\n"
            f"💰 Баланс: {xp} XP 🎲",
            parse_mode="HTML"
        )

# ========== ФЕРМЫ ==========
@dp.message(Command("farms"))
async def farms_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    farms = get_farms(username)
    
    if not farms:
        text = f"""🏭 <b>У тебя пока нет ферм!</b> 🏭

Доступные фермы:
🕷️ <b>Пауки</b> - 1000 XP (50/час)
🧟 <b>Зомби</b> - 1000 XP (75/час)
💥 <b>Криперы</b> - 1000 XP (100/час)
🏹 <b>Скелеты</b> - 1000 XP (60/час)
👾 <b>Эндермены</b> - 1500 XP (150/час)

📝 /buy_farm <название> - купить ферму
💰 /claim - собрать опыт

Пример: /buy_farm криперов"""
        await message.answer(text, parse_mode="HTML")
        return
    
    text = "🏭 <b>ТВОИ ФЕРМЫ</b> 🏭\n\n"
    total_income = 0
    farm_emoji = {"пауков": "🕷️", "зомби": "🧟", "криперов": "💥", "скелетов": "🏹", "эндерменов": "👾"}
    farm_base = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
    
    for name, data in farms.items():
        emoji = farm_emoji.get(name, "🏭")
        base = farm_base.get(name, 50)
        level = data.get("level", 1)
        income = base * level
        total_income += income
        text += f"{emoji} <b>{name}</b>: ур. {level} ({income} XP/час)\n"
    
    text += f"\n📈 <b>Общий доход:</b> {total_income} XP/час"
    text += f"\n💰 /claim - собрать опыт"
    text += f"\n⬆️ /upgrade_farm <название> - улучшить ферму"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("buy_farm"))
async def buy_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    response = await get_enderia_response(message.text, username, bot=bot, chat_id=message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("upgrade_farm"))
async def upgrade_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    response = await get_enderia_response(message.text, username, bot=bot, chat_id=message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("claim"))
async def claim_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    response = await get_enderia_response("/claim", username, bot=bot, chat_id=message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    response = await get_enderia_response("/leaderboard", username, bot=bot, chat_id=message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""🎮 <b>ДОСТУПНЫЕ КОМАНДЫ</b> 🎮

💰 <b>БАЛАНС:</b>
/balance - баланс опыта
/profile - профиль
/daily - бонус 500 XP

🎲 <b>ИГРЫ:</b>
/bet [сумма] - игра в кости (x2)

🏭 <b>ФЕРМЫ:</b>
/farms - мои фермы
/buy_farm <название> - купить ферму
/upgrade_farm <название> - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

💎 <b>Стартовый баланс: 1000 XP</b>
🎲 <b>Минимальная ставка: 50 XP</b>

🎁 <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!

🐱 Напиши /bet 100 чтобы сыграть! 💜"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""💜 <b>Помощь по боту LostEarth</b> 💜

🏠 <b>Команды сервера:</b>
/start - Главное меню
/online - Показать онлайн

💰 <b>БАЛАНС:</b>
/balance - баланс опыта
/profile - профиль
/daily - бонус 500 XP

🎲 <b>ИГРЫ:</b>
/bet [сумма] - игра в кости (x2)

🏭 <b>ФЕРМЫ:</b>
/farms - мои фермы
/buy_farm <название> - купить ферму
/upgrade_farm <название> - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

💎 <b>Стартовый баланс: 1000 XP</b>
🎲 <b>Минимальная ставка: 50 XP</b>
🎁 <b>Ежедневный бонус: 500 XP</b>

🐱 <i>Удачи в игре и фарме!</i> 💜"""
    await message.answer(text, parse_mode="HTML")

# ========== ОБРАБОТЧИК ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    print(f"📥 Получено от {username}: {user_message}")
    save_to_log(username, user_message, is_bot=False)
    
    last_active[username] = datetime.now()
    user_bio = await get_user_bio(message.from_user.id)
    
    if user_message.startswith("/"):
        return
    
    if should_respond(user_message):
        print(f"🎯 Эндерия отвечает {username}")
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(user_message, username, is_reply=False, chat_id=message.chat.id, bot=bot, user_bio=user_bio)
        if response:
            await message.reply(response, parse_mode="HTML")
            print(f"✅ Ответ отправлен {username}")

# ========== КОЛБЭКИ ==========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    
    if data == "menu_main":
        online, max_players = await get_server_online()
        text = f"💜 <b>Главное меню</b>\n\n📊 Онлайн: {online}/{max_players}\n\n🐱 /games - игры, /farms - фермы"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        text = f"""👑 <b>LOSTEARTH</b> 👑

💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>
📊 <b>Онлайн:</b> {online}/{max_players}

🐰 <i>Приятной игры!</i>"""
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_premium":
        text = f"""👑 <b>ПРЕМИУМ ДОСТУП</b> 👑

🌿 <b>Друид</b> - 50₽
🔮 <b>Оракул</b> - 100₽
👑 <b>Монарх</b> - 200₽
🪽 <b>Херувим</b> - 300₽ (полёт!)
🏛️ <b>Архонт</b> - 400₽
😇 <b>Серафим</b> - 600₽

📩 <b>По вопросам:</b> @pelmewki379

🐱 <i>Хочешь полёт? Бери Херувима!</i>"""
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_enderia":
        text = f"""💜 <b>Эндерия - твой живой помощник</b> 💜

🐱 <b>Кто я?</b>
Я девушка-эндермен, хранительница Края. Сама играю на сервере и фармлю опыт!

📝 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди

💰 <b>Игры и фермы:</b>
/bet, /balance, /profile, /daily
/farms, /buy_farm, /upgrade_farm, /claim

🎁 <b>Ежедневный бонус 500 XP</b>
Добавь @lostearth_bot в описание профиля!

🐰 <i>Строй фермы, копи опыт, становись лучшим!</i>
💜"""
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_farms":
        await callback.message.edit_text("🏭 /farms - посмотреть свои фермы", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_top":
        await callback.message.edit_text("🏆 /leaderboard - топ игроков по опыту", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🤖 Бот: @{bot_info.username}")
    print("💰 Игры: /bet, /balance, /profile, /daily")
    print("🏭 Фермы: /farms, /buy_farm, /upgrade_farm, /claim")
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
