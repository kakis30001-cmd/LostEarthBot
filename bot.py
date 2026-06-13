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
    set_server_online,
    save_to_log,
    E_CAT_DANCE,
    E_CAT_OK,
    E_CAT_UP,
    E_CAT_SURPRISED,
    E_RABBIT,
    E_ANIME,
    E_HEART,
    E_CROWN,
    E_HOUSE,
    E_NOTE,
    E_MAGIC,
    E_JOYSTICK,
)

from games import (
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
    init_player,
    game_dice_bet,
    game_football_bet,
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

# ID ДЛЯ КНОПОК
BUTTON_EMOJI_ID = {
    "door": "5873147866364514353",
    "note": "5870930744116776638",
    "rabbit_fly": "5217576088506505749",
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "joystick": "5870717606364713020",
}

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
        [InlineKeyboardButton(text="IP И ОНЛАЙН", callback_data="menu_ip", icon_custom_emoji_id=BUTTON_EMOJI_ID["door"])],
        [InlineKeyboardButton(text="ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL), icon_custom_emoji_id=BUTTON_EMOJI_ID["note"]),
         InlineKeyboardButton(text="ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL), icon_custom_emoji_id=BUTTON_EMOJI_ID["rabbit_fly"])],
        [InlineKeyboardButton(text="ПРЕМИУМ", callback_data="menu_premium", icon_custom_emoji_id=BUTTON_EMOJI_ID["crown"]),
         InlineKeyboardButton(text="ЭНДИ", callback_data="menu_enderia", icon_custom_emoji_id=BUTTON_EMOJI_ID["cat_ok"])],
        [InlineKeyboardButton(text="ФЕРМЫ", callback_data="menu_farms", icon_custom_emoji_id=BUTTON_EMOJI_ID["house"]),
         InlineKeyboardButton(text="ТОП", callback_data="menu_top", icon_custom_emoji_id=BUTTON_EMOJI_ID["crown"])]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ОБНОВИТЬ", callback_data="refresh_online", icon_custom_emoji_id=BUTTON_EMOJI_ID["check"])],
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])]
    ])

# ========== КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    init_player(username)
    online, max_players = await get_server_online()
    
    text = f"""{E_MAGIC} <b>Добро пожаловать на {SERVER['name']}</b> {E_MAGIC}

{E_HOUSE} <b>{SERVER['mode']}</b>

{E_CAT_DANCE} <b>Я Энди - твой живой помощник!</b>

{E_CROWN} <b>Текущий онлайн:</b> {online}/{max_players}

{E_CROWN} <b>Стартовый баланс: 1000 XP</b>
{E_HEART} <b>Как получить бонус?</b>
Добавь @lostearth_bot в описание профиля!

{E_RABBIT} {E_ANIME} {E_CAT_DANCE}

📝 <b>Доступные команды:</b>
/games - список всех игр и ферм
/balance - баланс опыта
/profile - твой профиль
/daily - бонус 500 XP"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{E_CROWN} <b>Онлайн: {online}/{max_players}</b> {E_CAT_DANCE}", parse_mode="HTML")

@dp.message(Command("balance"))
@dp.message(Command("bal"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    await message.answer(f"{E_CROWN} {username}, твой баланс: {xp} XP! {E_JOYSTICK}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    stats = get_stats(username)
    farms = get_farms(username)
    farm_count = len(farms)
    total_income = calculate_income(farms)
    
    text = f"""{E_CROWN} <b>ПРОФИЛЬ ИГРОКА</b> {E_CROWN}

{E_HOUSE} Имя: {username}
{E_CROWN} Опыт: {xp} XP
{E_JOYSTICK} Побед: {stats['wins']}
{E_HEART} Поражений: {stats['losses']}
{E_NOTE} Ферм: {farm_count}
{E_MAGIC} Доход в час: {total_income} XP

{E_MAGIC} <b>Ежедневный бонус: +500 XP</b>
{E_NOTE} Добавь в описание: @lostearth_bot

{E_CAT_OK} /daily - получить бонус! {E_HEART}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    if not has_bot_in_bio:
        text = f"""{E_CAT_SURPRISED} <b>НЕТ БОНУСА!</b> {E_CAT_SURPRISED}

Чтобы получать ежедневный бонус 500 XP, добавь в описание своего профиля:

<b>@lostearth_bot</b>

{E_NOTE} <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

{E_HEART} После добавления напиши /daily снова! {E_CAT_OK}"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if can_claim_daily_bonus(username):
        amount = claim_daily_bonus(username)
        xp = get_xp(username)
        text = f"{E_MAGIC} <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> {E_MAGIC}\n\n{E_CROWN} +{amount} XP!\n{E_HOUSE} Баланс: {xp} XP\n\n{E_RABBIT} Заходи завтра снова! {E_HEART}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{E_HEART} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {E_CAT_OK}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("bet"))
async def bet_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    match = re.match(r"^/bet\s+(\d+)$", message.text)
    if not match:
        await message.answer(f"{E_JOYSTICK} Используй: /bet [сумма]\n{E_CROWN} Минимальная ставка: 50 XP\nПример: /bet 100", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    response = await game_dice_bet(username, bet_amount, bot, message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("football"))
@dp.message(Command("foot"))
async def football_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    match = re.match(r"^/(?:football|foot)\s+(\d+)$", message.text)
    if not match:
        await message.answer(f"⚽ Используй: /football [сумма]\n{E_CROWN} Минимальная ставка: 50 XP\nПример: /football 100", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    response = await game_football_bet(username, bet_amount, bot, message.chat.id)
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("farms"))
async def farms_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    farms = get_farms(username)
    
    if not farms:
        text = f"""{E_HOUSE} <b>У тебя пока нет ферм!</b> {E_HOUSE}

Доступные фермы:
🕷️ <b>Пауки</b> - 1000 XP (50/час)
🧟 <b>Зомби</b> - 1000 XP (75/час)
💥 <b>Криперы</b> - 1000 XP (100/час)
🏹 <b>Скелеты</b> - 1000 XP (60/час)
👾 <b>Эндермены</b> - 1500 XP (150/час)

{E_NOTE} /buy_farm <название> - купить ферму
{E_MAGIC} /claim - собрать опыт

Пример: /buy_farm криперов"""
        await message.answer(text, parse_mode="HTML")
        return
    
    text = f"{E_HOUSE} <b>ТВОИ ФЕРМЫ</b> {E_HOUSE}\n\n"
    total_income = 0
    farm_emoji = {"пауков": "🕷️", "зомби": "🧟", "криперов": "💥", "скелетов": "🏹", "эндерменов": "👾"}
    farm_base = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
    
    for name, data in farms.items():
        emoji_farm = farm_emoji.get(name, "🏭")
        base = farm_base.get(name, 50)
        level = data.get("level", 1)
        income = base * level
        total_income += income
        text += f"{emoji_farm} <b>{name}</b>: ур. {level} ({income} XP/час)\n"
    
    text += f"\n{E_CROWN} <b>Общий доход:</b> {total_income} XP/час"
    text += f"\n{E_MAGIC} /claim - собрать опыт"
    text += f"\n{E_CAT_UP} /upgrade_farm <название> - улучшить ферму"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("buy_farm"))
async def buy_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(f"{E_NOTE} Используй: /buy_farm <название>\n\nДоступны: пауков, зомби, криперов, скелетов, эндерменов", parse_mode="HTML")
        return
    
    farm_name = parts[1].lower()
    farm_map = {
        "пауков": "пауков", "паук": "пауков",
        "зомби": "зомби", "зомб": "зомби",
        "криперов": "криперов", "крипер": "криперов",
        "скелетов": "скелетов", "скелет": "скелетов",
        "эндерменов": "эндерменов", "эндермен": "эндерменов"
    }
    
    if farm_name not in farm_map:
        await message.answer(f"{E_CAT_SURPRISED} Ферма не найдена!", parse_mode="HTML")
        return
    
    success, msg = buy_farm(username, farm_map[farm_name])
    await message.answer(msg, parse_mode="HTML")

@dp.message(Command("upgrade_farm"))
async def upgrade_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(f"{E_NOTE} Используй: /upgrade_farm <название>\n\nПример: /upgrade_farm криперов", parse_mode="HTML")
        return
    
    farm_name = parts[1].lower()
    farm_map = {
        "пауков": "пауков", "паук": "пауков",
        "зомби": "зомби", "зомб": "зомби",
        "криперов": "криперов", "крипер": "криперов",
        "скелетов": "скелетов", "скелет": "скелетов",
        "эндерменов": "эндерменов", "эндермен": "эндерменов"
    }
    
    if farm_name not in farm_map:
        await message.answer(f"{E_CAT_SURPRISED} Ферма не найдена!", parse_mode="HTML")
        return
    
    success, msg = upgrade_farm(username, farm_map[farm_name])
    await message.answer(msg, parse_mode="HTML")

@dp.message(Command("claim"))
async def claim_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    income = claim_income(username)
    if income > 0:
        xp = get_xp(username)
        await message.answer(f"{E_MAGIC} <b>Собрано {income} XP</b> с ферм! {E_MAGIC}\n\n{E_CROWN} Твой опыт: {xp} XP {E_CAT_DANCE}", parse_mode="HTML")
    else:
        farms = get_farms(username)
        if not farms:
            await message.answer(f"{E_HOUSE} У тебя нет ферм! Купи первую: /buy_farm пауков {E_RABBIT}", parse_mode="HTML")
        else:
            await message.answer(f"{E_NOTE} Пока не накопилось опыта. Подожди немного или улучшай фермы! {E_CAT_UP}", parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    leaders = get_leaderboard(10)
    if not leaders:
        await message.answer(f"{E_CROWN} Пока нет игроков в топе! Будь первым! {E_MAGIC}", parse_mode="HTML")
        return
    
    text = f"{E_CROWN} <b>ТОП ИГРОКОВ ПО ОПЫТУ</b> {E_CROWN}\n\n"
    for i, p in enumerate(leaders, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} <b>{p['username']}</b> - {p['xp']} XP (ферм: {p['farms_count']})\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{E_JOYSTICK} <b>ДОСТУПНЫЕ ИГРЫ И ФЕРМЫ</b> {E_JOYSTICK}

{E_CROWN} <b>БАЛАНС:</b>
/balance - баланс опыта
/profile - профиль игрока
/daily - бонус 500 XP

{E_JOYSTICK} <b>ИГРЫ:</b>
🎲 /bet [сумма] - игра в кости (выигрыш x2)
⚽ /football [сумма] - футбол (гол = x2)

{E_HOUSE} <b>ФЕРМЫ:</b>
/farms - мои фермы
/buy_farm <название> - купить ферму
/upgrade_farm <название> - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

{E_CROWN} <b>Стартовый баланс: 1000 XP</b>
{E_JOYSTICK} <b>Минимальная ставка: 50 XP</b>

{E_HEART} <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""{E_HEART} <b>Помощь по боту LostEarth</b> {E_HEART}

{E_HOUSE} <b>Команды сервера:</b>
/start - Главное меню
/online - Показать онлайн

{E_CROWN} <b>БАЛАНС:</b>
/balance - баланс опыта
/profile - профиль игрока
/daily - бонус 500 XP

{E_JOYSTICK} <b>ИГРЫ:</b>
🎲 /bet [сумма] - игра в кости (x2)
⚽ /football [сумма] - футбол (гол = x2)

{E_HOUSE} <b>ФЕРМЫ:</b>
/farms - мои фермы
/buy_farm <название> - купить ферму
/upgrade_farm <название> - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

{E_CROWN} <b>Стартовый баланс: 1000 XP</b>
{E_JOYSTICK} <b>Минимальная ставка: 50 XP</b>
{E_MAGIC} <b>Ежедневный бонус: 500 XP</b>

{E_CAT_DANCE} <i>Удачи в игре и фарме!</i> {E_HEART}"""
    await message.answer(text, parse_mode="HTML")

# ========== ОБРАБОТЧИК ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    if user_message.startswith("/"):
        return
    
    # Проверяем, является ли это ответом на сообщение бота
    is_reply_to_bot = False
    if message.reply_to_message:
        if message.reply_to_message.from_user.id == bot.id:
            is_reply_to_bot = True
    
    if should_respond(user_message) or is_reply_to_bot:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        user_bio = await get_user_bio(message.from_user.id)
        response = await get_enderia_response(user_message, username, is_reply=is_reply_to_bot, user_bio=user_bio)
        if response:
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    
    if data == "menu_main":
        online, max_players = await get_server_online()
        text = f"{E_HEART} <b>Главное меню</b>\n\n{E_CROWN} Онлайн: {online}/{max_players}\n\n{E_CAT_DANCE} /games - все команды"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        text = f"{E_CROWN} <b>LOSTEARTH</b> {E_CROWN}\n\n{E_HOUSE} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>Онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer()
    
    elif data == "refresh_online":
        online_cache.clear()
        last_update.clear()
        online, max_players = await get_server_online()
        text = f"{E_CROWN} <b>LOSTEARTH</b> {E_CROWN}\n\n{E_HOUSE} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>Онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer("🔄 Онлайн обновлён!")
    
    elif data == "menu_premium":
        text = f"{E_CROWN} <b>ПРЕМИУМ ДОСТУП</b> {E_CROWN}\n\n{E_MAGIC} <b>Друид</b> - 50₽\n{E_NOTE} <b>Оракул</b> - 100₽\n{E_CROWN} <b>Монарх</b> - 200₽\n{E_RABBIT} <b>Херувим</b> - 300₽ (полёт!)\n{E_HOUSE} <b>Архонт</b> - 400₽\n{E_CAT_DANCE} <b>Серафим</b> - 600₽\n\n{E_HEART} <b>По вопросам:</b> @pelmewki379"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_enderia":
        text = f"{E_HEART} <b>Энди - твой живой помощник</b> {E_HEART}\n\n{E_CAT_DANCE} <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n{E_NOTE} <b>Как ко мне обратиться:</b>\nНапиши: Энди\n\n{E_JOYSTICK} <b>Игры и фермы:</b>\n/games - список всех команд\n\n{E_MAGIC} <b>Ежедневный бонус 500 XP</b>\nДобавь @lostearth_bot в описание профиля!"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_farms":
        await callback.message.edit_text(f"{E_HOUSE} /farms - посмотреть свои фермы", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_top":
        await callback.message.edit_text(f"{E_CROWN} /leaderboard - топ игроков по опыту", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🤖 Бот: @{bot_info.username}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
