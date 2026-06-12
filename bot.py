import asyncio
import os
import socket
import struct
import json
from datetime import datetime
from threading import Thread
import random
import re

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
    game_dice_bet,
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

# ========== ПРЕМИУМ ЭМОДЗИ ==========
EMOJI = {
    "cat_dance": '<tg-emoji emoji-id="5359444458930718519">🐱</tg-emoji>',
    "cat_ok": '<tg-emoji emoji-id="5269476765369144234">🤙</tg-emoji>',
    "cat_up": '<tg-emoji emoji-id="5269698007724499331">👍</tg-emoji>',
    "cat_laugh": '<tg-emoji emoji-id="5276391181679366784">😂</tg-emoji>',
    "cat_kiss": '<tg-emoji emoji-id="6325462176660195024">😘</tg-emoji>',
    "cat_surprised": '<tg-emoji emoji-id="5269649173946345008">😲</tg-emoji>',
    "rabbit_fly": '<tg-emoji emoji-id="5217576088506505749">🐰</tg-emoji>',
    "anime_dance": '<tg-emoji emoji-id="6325682031741109665">💃</tg-emoji>',
    "heart": '<tg-emoji emoji-id="5199427253225667842">💜</tg-emoji>',
    "crown": '<tg-emoji emoji-id="5807868868886009920">👑</tg-emoji>',
    "house": '<tg-emoji emoji-id="5873147866364514353">🏠</tg-emoji>',
    "note": '<tg-emoji emoji-id="5870930744116776638">📝</tg-emoji>',
    "magic": '<tg-emoji emoji-id="5474144592817318927">✨</tg-emoji>',
    "joystick": '<tg-emoji emoji-id="5870717606364713020">🎮</tg-emoji>',
    "door": '<tg-emoji emoji-id="5873147866364514353">🚪</tg-emoji>',
    "check": '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji>',
    "back": '<tg-emoji emoji-id="5875082500023258804">◀️</tg-emoji>',
}

def random_cat():
    cats = [EMOJI["cat_dance"], EMOJI["cat_ok"], EMOJI["cat_up"], EMOJI["cat_laugh"], EMOJI["cat_kiss"]]
    return random.choice(cats)

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

# ========== КОНФИГ ==========
SERVER = {
    "name": "LostEarth",
    "mode": "Мирный режим по заявкам!",
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
    except Exception as e:
        print(f"Ошибка получения статуса: {e}")
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
         InlineKeyboardButton(text="ЭНДЕРИЯ", callback_data="menu_enderia", icon_custom_emoji_id=BUTTON_EMOJI_ID["cat_ok"])],
        [InlineKeyboardButton(text="🏭 ФЕРМЫ", callback_data="menu_farms", icon_custom_emoji_id=BUTTON_EMOJI_ID["house"]),
         InlineKeyboardButton(text="👑 ТОП", callback_data="menu_top", icon_custom_emoji_id=BUTTON_EMOJI_ID["crown"])]
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

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    init_player(username)
    online, max_players = await get_server_online()
    
    text = f"""{EMOJI['magic']} <b>Добро пожаловать на {SERVER['name']}</b> {EMOJI['magic']}

{EMOJI['house']} <b>{SERVER['mode']}</b>

{random_cat()} <b>Я Эндерия - твой живой помощник!</b>

{EMOJI['crown']} <b>Текущий онлайн:</b> {online}/{max_players}

{EMOJI['joystick']} <b>ИГРЫ:</b>
🎲 /bet [сумма] - игра в кости (x2 выигрыш)
👑 /balance - твой опыт
👤 /profile - твой профиль
🎁 /daily - бонус 500 XP

{EMOJI['house']} <b>ФЕРМЫ ОПЫТА:</b>
🏭 /farms - твои фермы
💰 /buy_farm - купить ферму
⬆️ /upgrade_farm - улучшить ферму
📦 /claim - собрать опыт
🏆 /leaderboard - топ игроков

{EMOJI['heart']} <b>Как получить бонус?</b>
Добавь @lostearth_bot в описание профиля!

{EMOJI['rabbit_fly']} {EMOJI['anime_dance']} {random_cat()}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{EMOJI['crown']} <b>Онлайн: {online}/{max_players}</b> {random_cat()}", parse_mode="HTML")

@dp.message(Command("balance"))
@dp.message(Command("bal"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    await message.answer(f"{EMOJI['crown']} {username}, твой баланс: {xp} XP! {random_cat()}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = get_xp(username)
    stats = get_stats(username)
    farms = get_farms(username)
    farm_count = len(farms)
    total_income = calculate_income(farms)
    
    text = f"""{EMOJI['crown']} <b>ПРОФИЛЬ ИГРОКА</b> {EMOJI['crown']}

{EMOJI['house']} Имя: {username}
{EMOJI['crown']} Опыт: {xp} XP
{EMOJI['joystick']} Побед: {stats['wins']}
{EMOJI['heart']} Поражений: {stats['losses']}
{EMOJI['note']} Всего игр: {stats['wins'] + stats['losses']}
🏭 Ферм: {farm_count}
📈 Доход в час: {total_income} XP

{EMOJI['magic']} <b>Ежедневный бонус: +500 XP</b>
{EMOJI['note']} Добавь в описание: @lostearth_bot

{random_cat()} /daily - получить бонус! {EMOJI['heart']}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    if not has_bot_in_bio:
        text = f"""{EMOJI['cat_surprised']} <b>НЕТ БОНУСА!</b> {EMOJI['cat_surprised']}

Чтобы получать ежедневный бонус 500 XP, добавь в описание своего профиля:

<b>@lostearth_bot</b>

{EMOJI['note']} <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

{EMOJI['heart']} После добавления напиши /daily снова! {random_cat()}"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if can_claim_daily_bonus(username):
        amount = claim_daily_bonus(username)
        xp = get_xp(username)
        text = f"{EMOJI['magic']} <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> {EMOJI['magic']}\n\n{EMOJI['crown']} +{amount} XP!\n{EMOJI['house']} Баланс: {xp} XP\n\n{EMOJI['rabbit_fly']} Заходи завтра снова! {EMOJI['heart']}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{EMOJI['heart']} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {random_cat()}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("bet"))
async def bet_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    match = re.match(r"^/bet\s+(\d+)$", user_message)
    if not match:
        await message.answer(f"{EMOJI['joystick']} {username}, используй: /bet [сумма] (например /bet 100)\n{EMOJI['crown']} Минимальная ставка: 50 XP", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    xp = get_xp(username)
    
    if bet_amount < 50:
        await message.answer(f"{EMOJI['joystick']} {username}, минимальная ставка 50 XP! {EMOJI['crown']}", parse_mode="HTML")
        return
    
    if xp < bet_amount:
        await message.answer(f"{EMOJI['heart']} {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount} {EMOJI['crown']}", parse_mode="HTML")
        return
    
    await message.answer(f"{EMOJI['joystick']} {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, message.chat.id)
    
    await asyncio.sleep(1.5)
    await message.answer(f"{random_cat()} Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, message.chat.id)
    
    if player_value > bot_value:
        update_xp(username, bet_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        await message.answer(
            f"{EMOJI['cat_dance']} <b>ПОБЕДА!</b> {EMOJI['cat_dance']}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"{EMOJI['magic']} Ты выиграл {bet_amount} XP!\n"
            f"{EMOJI['crown']} Баланс: {new_xp} XP {EMOJI['heart']}",
            parse_mode="HTML"
        )
    elif player_value < bot_value:
        update_xp(username, -bet_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        await message.answer(
            f"{EMOJI['cat_surprised']} <b>ПРОИГРЫШ...</b> {EMOJI['cat_surprised']}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"{EMOJI['heart']} Ты проиграл {bet_amount} XP!\n"
            f"{EMOJI['crown']} Баланс: {new_xp} XP {random_cat()}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{EMOJI['heart']} <b>НИЧЬЯ!</b> {EMOJI['heart']}\n\n"
            f"Оба выбросили {player_value}\n\n"
            f"{EMOJI['crown']} Ставка возвращена!\n"
            f"{EMOJI['house']} Баланс: {xp} XP {EMOJI['joystick']}",
            parse_mode="HTML"
        )

# ========== ФЕРМЫ ==========
@dp.message(Command("farms"))
async def farms_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    farms = get_farms(username)
    
    if not farms:
        text = f"""{EMOJI['house']} <b>У тебя пока нет ферм!</b> {EMOJI['house']}

Доступные фермы:
🕷️ <b>Пауки</b> - 1000 XP (50/час)
🧟 <b>Зомби</b> - 1000 XP (75/час)
💥 <b>Криперы</b> - 1000 XP (100/час)
🏹 <b>Скелеты</b> - 1000 XP (60/час)
👾 <b>Эндермены</b> - 1500 XP (150/час)

{EMOJI['note']} /buy_farm <название> - купить ферму
{EMOJI['magic']} /claim - собрать опыт"""
        await message.answer(text, parse_mode="HTML")
        return
    
    text = f"{EMOJI['house']} <b>ТВОИ ФЕРМЫ</b> {EMOJI['house']}\n\n"
    total_income = 0
    for name, data in farms.items():
        farm_info = {
            "пауков": {"base": 50, "emoji": "🕷️"},
            "зомби": {"base": 75, "emoji": "🧟"},
            "криперов": {"base": 100, "emoji": "💥"},
            "скелетов": {"base": 60, "emoji": "🏹"},
            "эндерменов": {"base": 150, "emoji": "👾"},
        }.get(name, {"base": 50, "emoji": "🏭"})
        
        level = data.get("level", 1)
        income = farm_info["base"] * level
        total_income += income
        text += f"{farm_info['emoji']} <b>{name}</b>: ур. {level} ({income} XP/час)\n"
    
    text += f"\n{EMOJI['crown']} <b>Общий доход:</b> {total_income} XP/час\n"
    text += f"{EMOJI['note']} /claim - собрать опыт\n"
    text += f"{EMOJI['magic']} /upgrade_farm <название> - улучшить ферму"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("buy_farm"))
async def buy_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(f"{EMOJI['note']} Используй: /buy_farm <название>\n\nДоступны: пауков, зомби, криперов, скелетов, эндерменов", parse_mode="HTML")
        return
    
    farm_name = parts[1].lower()
    farms_map = {
        "пауков": "пауков", "паук": "пауков", "пауки": "пауков",
        "зомби": "зомби", "зомб": "зомби",
        "криперов": "криперов", "крипер": "криперов", "криперы": "криперов",
        "скелетов": "скелетов", "скелет": "скелетов", "скелеты": "скелетов",
        "эндерменов": "эндерменов", "эндермен": "эндерменов", "эндермены": "эндерменов"
    }
    
    if farm_name not in farms_map:
        await message.answer(f"{EMOJI['cat_surprised']} Ферма не найдена! Доступны: пауков, зомби, криперов, скелетов, эндерменов", parse_mode="HTML")
        return
    
    farm_key = farms_map[farm_name]
    success, msg = buy_farm(username, farm_key)
    
    if success:
        await message.answer(f"{EMOJI['cat_dance']} {msg} {EMOJI['magic']}\n\n{EMOJI['note']} Не забывай собирать опыт командой /claim!", parse_mode="HTML")
    else:
        await message.answer(f"{EMOJI['cat_surprised']} {msg}", parse_mode="HTML")

@dp.message(Command("upgrade_farm"))
async def upgrade_farm_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(f"{EMOJI['note']} Используй: /upgrade_farm <название>\n\nПример: /upgrade_farm криперов", parse_mode="HTML")
        return
    
    farm_name = parts[1].lower()
    farms_map = {
        "пауков": "пауков", "паук": "пауков",
        "зомби": "зомби", "зомб": "зомби",
        "криперов": "криперов", "крипер": "криперов",
        "скелетов": "скелетов", "скелет": "скелетов",
        "эндерменов": "эндерменов", "эндермен": "эндерменов"
    }
    
    if farm_name not in farms_map:
        await message.answer(f"{EMOJI['cat_surprised']} Ферма не найдена!", parse_mode="HTML")
        return
    
    farm_key = farms_map[farm_name]
    success, msg = upgrade_farm(username, farm_key)
    
    if success:
        await message.answer(f"{EMOJI['cat_up']} {msg} {EMOJI['crown']}", parse_mode="HTML")
    else:
        await message.answer(f"{EMOJI['cat_surprised']} {msg}", parse_mode="HTML")

@dp.message(Command("claim"))
async def claim_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    income = claim_income(username)
    
    if income > 0:
        xp = get_xp(username)
        await message.answer(f"{EMOJI['magic']} <b>Собрано {income} XP</b> с ферм! {EMOJI['magic']}\n\n{EMOJI['crown']} Твой опыт: {xp} XP {random_cat()}", parse_mode="HTML")
    else:
        await message.answer(f"{EMOJI['house']} Пока не накопилось опыта с ферм. Подожди немного или улучшай фермы! {EMOJI['heart']}\n\n{EMOJI['note']} /upgrade_farm <название> - улучшить ферму", parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    leaders = get_leaderboard(10)
    
    if not leaders:
        await message.answer(f"{EMOJI['crown']} Пока нет игроков в топе! Будь первым! {EMOJI['magic']}", parse_mode="HTML")
        return
    
    text = f"{EMOJI['crown']} <b>ТОП ИГРОКОВ ПО ОПЫТУ</b> {EMOJI['crown']}\n\n"
    for i, p in enumerate(leaders, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} <b>{p['username']}</b> - {p['xp']} XP (ферм: {p['farms_count']})\n"
    
    text += f"\n{EMOJI['joystick']} Хочешь в топ? Строй фермы и играй в /bet!"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{EMOJI['joystick']} <b>ДОСТУПНЫЕ ИГРЫ</b> {EMOJI['joystick']}

{EMOJI['crown']} <b>/bet [сумма]</b> - игра в кости (x2 выигрыш)
{EMOJI['house']} <b>/balance</b> - показать баланс
{EMOJI['heart']} <b>/profile</b> - твой профиль
{EMOJI['magic']} <b>/daily</b> - бонус 500 XP

{EMOJI['house']} <b>ФЕРМЫ ОПЫТА:</b>
🏭 /farms - твои фермы
💰 /buy_farm - купить ферму
⬆️ /upgrade_farm - улучшить ферму
📦 /claim - собрать опыт
🏆 /leaderboard - топ игроков

{EMOJI['crown']} <b>Стартовый баланс: 1000 XP</b>
{EMOJI['joystick']} <b>Минимальная ставка: 50 XP</b>

{EMOJI['heart']} <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!

{EMOJI['rabbit_fly']} Напиши /bet 100 чтобы сыграть! {random_cat()}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""{EMOJI['heart']} <b>Помощь по боту LostEarth</b> {EMOJI['heart']}

{EMOJI['house']} <b>Команды сервера:</b>
/start - Главное меню
/online - Показать онлайн

{EMOJI['joystick']} <b>Игры:</b>
/bet [сумма] - игра в кости (x2)
/balance - баланс опыта
/profile - профиль
/daily - бонус 500 XP

{EMOJI['house']} <b>Фермы:</b>
/farms - мои фермы
/buy_farm - купить ферму
/upgrade_farm - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

{EMOJI['heart']} <b>Как получить бонус?</b>
Добавь @lostearth_bot в описание профиля!

{EMOJI['magic']} <b>Правила игры:</b>
• Минимальная ставка: 50 XP
• Выигрыш: x2 от ставки

{random_cat()} <i>Удачи в игре и фарме!</i>"""
    await message.answer(text, parse_mode="HTML")

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    print(f"📥 Получено от {username}: {user_message}")
    save_to_log(username, user_message, is_bot=False)
    
    # Обновляем активность
    from enderia import last_active
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
async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        if "query is too old" not in str(e):
            print(f"[ERROR] {e}")

@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    username = callback.from_user.username or callback.from_user.first_name
    
    if data == "menu_main":
        online, max_players = await get_server_online()
        text = f"{EMOJI['heart']} <b>Главное меню</b>\n\n{EMOJI['crown']} Онлайн: {online}/{max_players}\n\n{random_cat()} /games - игры, /farms - фермы"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)
    
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        text = f"{EMOJI['crown']} <b>LOSTEARTH</b> {EMOJI['crown']}\n\n{EMOJI['house']} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{EMOJI['note']} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{EMOJI['crown']} <b>Онлайн:</b> {online}/{max_players}\n\n{EMOJI['rabbit_fly']} <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback)
    
    elif data == "refresh_online":
        online_cache.clear()
        last_update.clear()
        online, max_players = await get_server_online()
        text = f"{EMOJI['crown']} <b>LOSTEARTH</b> {EMOJI['crown']}\n\n{EMOJI['house']} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{EMOJI['note']} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{EMOJI['crown']} <b>Онлайн:</b> {online}/{max_players}\n\n{EMOJI['rabbit_fly']} <i>Приятной игры!</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback, "Онлайн обновлён!")
    
    elif data == "menu_premium":
        text = f"{EMOJI['crown']} <b>ПРЕМИУМ ДОСТУП</b> {EMOJI['crown']}\n\n{EMOJI['magic']} <b>Друид</b> - 50₽\n{EMOJI['note']} <b>Оракул</b> - 100₽\n{EM
