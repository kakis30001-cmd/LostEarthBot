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

# ========== ПРЕМИУМ ЭМОДЗИ (ВСЕ ЭМОДЗИ ТОЛЬКО ТУТ) ==========
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

# Функции для получения премиум эмодзи (БЕЗ ОБЫЧНЫХ ФОЛБЭКОВ)
def get_cat_dance():
    return premium_emoji(PREMIUM_EMOJI["cat_dance"], "")

def get_cat_ok():
    return premium_emoji(PREMIUM_EMOJI["cat_ok"], "")

def get_cat_up():
    return premium_emoji(PREMIUM_EMOJI["cat_up"], "")

def get_cat_laugh():
    return premium_emoji(PREMIUM_EMOJI["cat_laugh"], "")

def get_cat_kiss():
    return premium_emoji(PREMIUM_EMOJI["cat_kiss"], "")

def get_cat_surprised():
    return premium_emoji(PREMIUM_EMOJI["cat_surprised"], "")

def get_rabbit_fly():
    return premium_emoji(PREMIUM_EMOJI["rabbit_fly"], "")

def get_heart():
    return premium_emoji(PREMIUM_EMOJI["heart"], "")

def get_anime_dance():
    return premium_emoji(PREMIUM_EMOJI["anime_dance"], "")

def get_crown():
    return premium_emoji(PREMIUM_EMOJI["crown"], "")

def get_house():
    return premium_emoji(PREMIUM_EMOJI["house"], "")

def get_note():
    return premium_emoji(PREMIUM_EMOJI["note"], "")

def get_magic():
    return premium_emoji(PREMIUM_EMOJI["magic"], "")

def get_joystick():
    return premium_emoji(PREMIUM_EMOJI["joystick"], "")

def get_check():
    return premium_emoji(PREMIUM_EMOJI["check"], "")

def get_back_arrow():
    return premium_emoji(PREMIUM_EMOJI["back"], "")

def get_door():
    return premium_emoji(PREMIUM_EMOJI["door"], "")

def random_cat():
    cats = [get_cat_dance(), get_cat_ok(), get_cat_up(), get_cat_laugh(), get_cat_kiss()]
    return random.choice(cats)

def random_emoji():
    all_emojis = [get_cat_dance(), get_cat_ok(), get_cat_up(), get_cat_laugh(), get_cat_kiss(), get_rabbit_fly(), get_heart(), get_anime_dance(), get_magic(), get_crown()]
    return random.choice(all_emojis)

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

# ========== КЛАВИАТУРЫ (ВСЕ КНОПКИ С ПРЕМИУМ ЭМОДЗИ) ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{get_door()} IP И ОНЛАЙН", 
            callback_data="menu_ip"
        )],
        [InlineKeyboardButton(
            text=f"{get_note()} ПРАВИЛА", 
            web_app=WebAppInfo(url=RULES_URL)
        ),
        InlineKeyboardButton(
            text=f"{get_rabbit_fly()} ЗАЯВКА", 
            web_app=WebAppInfo(url=APPLY_URL)
        )],
        [InlineKeyboardButton(
            text=f"{get_crown()} ПРЕМИУМ", 
            callback_data="menu_premium"
        ),
        InlineKeyboardButton(
            text=f"{get_cat_ok()} ЭНДЕРИЯ", 
            callback_data="menu_enderia"
        )]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{get_check()} ОБНОВИТЬ", 
            callback_data="refresh_online"
        )],
        [InlineKeyboardButton(
            text=f"{get_back_arrow()} НАЗАД", 
            callback_data="menu_main"
        )]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{get_back_arrow()} НАЗАД", 
            callback_data="menu_main"
        )]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    online, max_players = await get_server_online()
    
    text = f"""{get_magic()} <b>Добро пожаловать на {SERVER['name']}</b> {get_magic()}

{get_house()} <b>{SERVER['mode']}</b>

{random_cat()} <b>Я Эндерия - твой живой помощник!</b>

{get_crown()} <b>Текущий онлайн:</b> {online}/{max_players}

{get_joystick()} <b>Игры с Эндерией:</b>
/bet [сумма] - Ставка на кубик (выигрыш х2)
/balance - Твой баланс
/profile - Твой профиль
/daily - Ежедневный бонус 100

{get_magic()} <b>Стартовый баланс: 100 алмазов</b>
{get_joystick()} <b>Минимальная ставка: 10 алмазов</b>

{get_heart()} <b>Как получить бонус?</b>
Добавь в описание профиля: @lostearth_bot

{get_rabbit_fly()} {get_anime_dance()} {random_cat()}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{get_crown()} <b>Онлайн: {online}/{max_players}</b> {random_cat()}", parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    size = get_memory_size(username)
    if size > 0:
        await message.answer(
            f"{random_cat()} <b>{username}, я помню наш диалог!</b>\n\n"
            f"{get_note()} Запомнено сообщений: {size}\n"
            f"{get_heart()} Очистить память: /clear_memory",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{get_heart()} <b>{username}, мы ещё не общались!</b>\n\n"
            f"{random_cat()} Напиши /games чтобы поиграть!",
            parse_mode="HTML"
        )

@dp.message(Command("clear_memory"))
async def clear_memory_cmd(message: Message):
    username = message.from_user.first_name or "Игрок"
    old_size = get_memory_size(username)
    clear_user_memory(username)
    await message.answer(
        f"{random_cat()} {get_magic()} <b>Память очищена!</b> {get_magic()}\n\n"
        f"{get_note()} Было запомнено: {old_size} сообщений",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = f"""{get_heart()} <b>Помощь по боту LostEarth</b> {get_heart()}

{get_house()} <b>Команды сервера:</b>
/start - Главное меню
/online - Показать онлайн

{get_joystick()} <b>Игры с Эндерией:</b>
/bet [сумма] - Ставка на кубик (выигрыш х2)
/balance - Показать баланс
/profile - Твой профиль
/daily - Ежедневный бонус 100

{get_heart()} <b>Как получить бонус?</b>
Добавь в описание профиля: @lostearth_bot

{get_magic()} <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Выигрыш: x2 от ставки

{random_cat()} <i>Удачи в игре!</i>"""
    await message.answer(text, parse_mode="HTML")

# ========== ИГРОВЫЕ КОМАНДЫ ==========
@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance(username)
    await message.answer(f"{get_crown()} {username}, твой баланс: {balance} алмазов! {random_cat()}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance(username)
    stats = get_stats(username)
    
    text = f"""{get_crown()} <b>ПРОФИЛЬ ИГРОКА</b> {get_crown()}

{get_house()} Имя: {username}
{get_crown()} Баланс: {balance} алмазов
{get_joystick()} Побед: {stats['wins']}
{get_heart()} Поражений: {stats['losses']}
{get_note()} Всего игр: {stats['wins'] + stats['losses']}

{get_magic()} <b>Ежедневный бонус: +100 алмазов</b>
{get_note()} Добавь в описание: @lostearth_bot

{random_cat()} Напиши /daily чтобы получить бонус! {get_heart()}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    from datetime import date
    username = message.from_user.username or message.from_user.first_name
    
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    if not has_bot_in_bio:
        text = f"""{get_cat_surprised()} <b>НЕТ БОНУСА!</b> {get_cat_surprised()}

Чтобы получать ежедневный бонус 100 алмазов, добавь в описание своего профиля:

<b>@lostearth_bot</b>

{get_note()} <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

{get_heart()} После добавления напиши /daily снова! {random_cat()}"""
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
        
        text = f"{get_magic()} <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> {get_magic()}\n\n{get_crown()} +100 алмазов!\n{get_house()} Баланс: {balance} алмазов\n\n{get_rabbit_fly()} Заходи завтра снова! {get_heart()}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{get_heart()} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {random_cat()}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("bet"))
async def bet_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    match = re.match(r"^/bet\s+(\d+)$", user_message)
    if not match:
        await message.answer(f"{get_joystick()} {username}, используй: /bet [сумма] (например /bet 50)\n{get_crown()} Минимальная ставка: 10 алмазов", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    balance = get_balance(username)
    
    if bet_amount < 10:
        await message.answer(f"{get_joystick()} {username}, минимальная ставка 10 алмазов! {get_crown()}", parse_mode="HTML")
        return
    
    if balance < bet_amount:
        await message.answer(f"{get_heart()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} {get_crown()}", parse_mode="HTML")
        return
    
    await message.answer(f"{get_joystick()} {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, message.chat.id)
    
    await asyncio.sleep(1.5)
    await message.answer(f"{random_cat()} Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, message.chat.id)
    
    if player_value > bot_value:
        update_balance(username, bet_amount)
        update_stats(username, is_win=True)
        new_balance = get_balance(username)
        await message.answer(
            f"{get_cat_dance()} <b>ПОБЕДА!</b> {get_cat_dance()}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"{get_magic()} Ты выиграл {bet_amount} алмазов!\n"
            f"{get_crown()} Баланс: {new_balance} {get_heart()}",
            parse_mode="HTML"
        )
    elif player_value < bot_value:
        update_balance(username, -bet_amount)
        update_stats(username, is_win=False)
        new_balance = get_balance(username)
        await message.answer(
            f"{get_cat_surprised()} <b>ПРОИГРЫШ...</b> {get_cat_surprised()}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"{get_heart()} Ты проиграл {bet_amount} алмазов!\n"
            f"{get_crown()} Баланс: {new_balance} {random_cat()}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{get_heart()} <b>НИЧЬЯ!</b> {get_heart()}\n\n"
            f"Оба выбросили {player_value}\n\n"
            f"{get_crown()} Ставка возвращена!\n"
            f"{get_house()} Баланс: {balance} {get_joystick()}",
            parse_mode="HTML"
        )

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{get_joystick()} <b>ДОСТУПНЫЕ ИГРЫ</b> {get_joystick()}

{get_crown()} <b>/bet [сумма]</b> - Ставка на кубик (выигрыш х2)
{get_house()} <b>/balance</b> - Показать баланс
{get_heart()} <b>/profile</b> - Твой профиль
{get_magic()} <b>/daily</b> - Ежедневный бонус 100

{get_magic()} <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Твой кубик против кубика Эндерии
• Если твой кубик больше - выигрываешь x2

{get_crown()} <b>Стартовый баланс: 100 алмазов</b>

{get_heart()} <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!

{get_joystick()} Напиши /bet 50 чтобы сыграть! {random_cat()}"""
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

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""{get_heart()} <b>Главное меню</b>\n\n{get_crown()} Онлайн: {online}/{max_players}\n\n{random_cat()} Напиши /games чтобы поиграть в кости!"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""{get_crown()} <b>LOSTEARTH</b> {get_crown()}

{get_house()} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
{get_note()} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>
{get_crown()} <b>Онлайн:</b> {online}/{max_players}

{get_rabbit_fly()} <i>Приятной игры!</i>"""
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
    text = f"""{get_crown()} <b>LOSTEARTH</b> {get_crown()}

{get_house()} <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>
{get_note()} <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>
{get_crown()} <b>Онлайн:</b> {online}/{max_players}

{get_rabbit_fly()} <i>Приятной игры!</i>"""
    chat_id = callback.message.chat.id
    last_online_data[chat_id] = {"online": online, "max": max_players}
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await safe_callback_answer(callback, "Онлайн обновлён!", False)
    except Exception as e:
        if "message is not modified" not in str(e):
            print(f"[ERROR] {e}")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{get_crown()} <b>ПРЕМИУМ ДОСТУП</b> {get_crown()}

{get_magic()} <b>Друид</b> - 50₽
{get_note()} <b>Оракул</b> - 100₽
{get_crown()} <b>Монарх</b> - 200₽
{get_rabbit_fly()} <b>Херувим</b> - 300₽ (полёт!)
{get_house()} <b>Архонт</b> - 400₽
{random_cat()} <b>Серафим</b> - 600₽

{get_heart()} <b>По вопросам:</b> @pelmewki379

{random_cat()} <i>Хочешь полёт? Бери Херувима!</i>"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        print(f"[ERROR] {e}")
    await safe_callback_answer(callback)

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{get_heart()} <b>Эндерия - твой живой помощник</b> {get_heart()}

{random_cat()} <b>Кто я?</b>
Я девушка-эндермен, хранительница Края.

{get_note()} <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди

{get_joystick()} <b>Игры:</b>
/bet, /balance, /profile, /daily

{get_magic()} <b>Ежедневный бонус 100</b>
Добавь @lostearth_bot в описание профиля!

{get_rabbit_fly()} <i>Просто позови меня по имени!</i>
{get_heart()}"""
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
    print("💰 Игры: /bet, /balance, /profile, /daily")
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
