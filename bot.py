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
)

from games import (
    get_xp,
    update_xp,
    get_stats,
    update_stats,
    get_farm_level,
    get_farm_info,
    start_farm_upgrade,
    claim_farm_income,
    get_leaderboard,
    can_claim_daily_bonus,
    claim_daily_bonus,
    init_player,
    game_dice_bet,
    SPIT_COST,
    FARM_LEVELS,
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
ENDERIA_EMOJI = {
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "cat_up": "5269698007724499331",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "heart": "5199427253225667842",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "magic": "5474144592817318927",
    "joystick": "5870717606364713020",
    "xp": "5258371229777165300",
    "spider": "5440875569984052896",
    "ender": "5440858845381402630",
    "skeleton": "5440858579093430128",
    "zombie": "5440655942536405315",
    "cat_rose": "5269347667242162562",
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CAT_DANCE = emoji(ENDERIA_EMOJI["cat_dance"], "🐱")
E_CAT_OK = emoji(ENDERIA_EMOJI["cat_ok"], "👍")
E_CAT_UP = emoji(ENDERIA_EMOJI["cat_up"], "👍")
E_CAT_SURPRISED = emoji(ENDERIA_EMOJI["cat_surprised"], "😲")
E_CAT_ROSE = emoji(ENDERIA_EMOJI["cat_rose"], "🌹")
E_RABBIT = emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")
E_ANIME = emoji(ENDERIA_EMOJI["anime_dance"], "💃")
E_HEART = emoji(ENDERIA_EMOJI["heart"], "💜")
E_CROWN = emoji(ENDERIA_EMOJI["crown"], "👑")
E_HOUSE = emoji(ENDERIA_EMOJI["house"], "🏠")
E_NOTE = emoji(ENDERIA_EMOJI["note"], "📝")
E_MAGIC = emoji(ENDERIA_EMOJI["magic"], "✨")
E_JOYSTICK = emoji(ENDERIA_EMOJI["joystick"], "🎮")
E_XP = emoji(ENDERIA_EMOJI["xp"], "⭐")

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
last_bot_message_id = {}

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
        [InlineKeyboardButton(text="🏭 ФЕРМА", callback_data="menu_farm"),
         InlineKeyboardButton(text="🎮 ИГРЫ", callback_data="menu_games")],
        [InlineKeyboardButton(text="🏆 ТОП", callback_data="menu_top")]
    ])

def get_farm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 СТАТУС ФЕРМЫ", callback_data="farm_status")],
        [InlineKeyboardButton(text="⬆️ УЛУЧШИТЬ ФЕРМУ", callback_data="farm_upgrade")],
        [InlineKeyboardButton(text="💰 ЗАБРАТЬ ДОХОД", callback_data="farm_claim")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

def get_games_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 СЫГРАТЬ В КОСТИ", callback_data="games_bet")],
        [InlineKeyboardButton(text="💰 МОЙ БАЛАНС", callback_data="games_balance")],
        [InlineKeyboardButton(text="👤 МОЙ ПРОФИЛЬ", callback_data="games_profile")],
        [InlineKeyboardButton(text="🎁 ДНЕВНОЙ БОНУС", callback_data="games_daily")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

def get_bet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 XP", callback_data="bet_50"),
         InlineKeyboardButton(text="100 XP", callback_data="bet_100"),
         InlineKeyboardButton(text="200 XP", callback_data="bet_200")],
        [InlineKeyboardButton(text="500 XP", callback_data="bet_500"),
         InlineKeyboardButton(text="1000 XP", callback_data="bet_1000"),
         InlineKeyboardButton(text="5000 XP", callback_data="bet_5000")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_games")]
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

# ========== КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    init_player(username)
    online, max_players = await get_server_online()
    xp = get_xp(username)
    
    text = f"""{E_MAGIC} <b>Добро пожаловать на {SERVER['name']}</b> {E_MAGIC}

{E_HOUSE} <b>Мирный режим по заявкам!</b>

{E_CAT_ROSE} <b>Я Эндерия - твой живой помощник!</b>

{E_XP} <b>Твой опыт:</b> {xp} XP

{E_HEART} <b>Дневной бонус:</b>
Добавь @lostearth_bot в описание профиля!

{E_CAT_DANCE} {E_RABBIT} {E_ANIME}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{E_CROWN} <b>Онлайн: {online}/{max_players}</b> {E_CAT_DANCE}", parse_mode="HTML")

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text.lower()
    user_id = message.from_user.id
    
    # Игра в кости по фразе "Энди кубик"
    if ("энди кубик" in user_message or "эндер кубик" in user_message or "кубик энди" in user_message) and should_respond(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await game_dice_bet(username, bot, message.chat.id, 50)
        await message.reply(response, parse_mode="HTML")
        return
    
    # Ставка с указанием суммы
    bet_match = re.search(r'ставка\s+(\d+)', user_message)
    if bet_match and should_respond(message.text):
        bet_amount = int(bet_match.group(1))
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await game_dice_bet(username, bot, message.chat.id, bet_amount)
        await message.reply(response, parse_mode="HTML")
        return
    
    # Забрать доход по фразе
    if ("забрать доход" in user_message or "собрать доход" in user_message or "забрать опыт" in user_message) and should_respond(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        income, hours_passed, farm_info = claim_farm_income(username)
        if income > 0:
            await message.reply(f"{E_MAGIC} <b>Собрано {income} XP</b> с фермы! {E_MAGIC}\n\n{E_XP} Твой опыт: {get_xp(username)} XP {E_CAT_DANCE}", parse_mode="HTML")
        else:
            await message.reply(f"{E_NOTE} Пока не накопилось опыта. Нужно подождать ещё {max(0, int(1 - hours_passed))} часа(ов) {E_CAT_SURPRISED}", parse_mode="HTML")
        return
    
    # Проверка на ответ на сообщение
    is_reply_to_bot = False
    replied_username = None
    replied_user_id = None
    
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        if replied_user:
            replied_user_id = replied_user.id
            replied_username = replied_user.first_name or replied_user.username
            if replied_user_id == bot.id:
                is_reply_to_bot = True
    
    # Если ответ на сообщение бота
    if is_reply_to_bot:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await get_enderia_response(message.text, username, is_reply=True, user_bio="")
        if response:
            await message.reply(response, parse_mode="HTML")
        return
    
    # Если ответ на сообщение другого человека И есть слово "плюнуть" (тратим 10 XP)
    if message.reply_to_message and replied_username and replied_user_id != bot.id and ("плюнуть" in user_message or "плюнь" in user_message):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        xp = get_xp(username)
        if xp < SPIT_COST:
            await message.reply(f"{E_CAT_SURPRISED} Не хватает {SPIT_COST} XP для плювка! У тебя {xp} XP", parse_mode="HTML")
            return
        
        update_xp(username, -SPIT_COST)
        
        reactions = [
            f"Ой-ой, кто тут ссорится? Лучше мириться! {E_HEART}",
            f"Фу, так некультурно! {E_CAT_SURPRISED}",
            f"Эй-эй, без рук! {E_CAT_DANCE}",
            f"Надеюсь, вы помиритесь! {E_CAT_ROSE}",
            f"Ай-яй-яй, нехорошо так делать! {E_CAT_OK}",
            f"Может, лучше в кости сыграете? {E_JOYSTICK}",
            f"Эндерия не одобряет! {E_CAT_SURPRISED}",
            f"Телепортируюсь от скандала! {E_MAGIC}",
        ]
        
        enderia_response = random.choice(reactions)
        await message.reply(f"{E_CAT_SURPRISED} <b>{username}</b> плюнул(а) на <b>{replied_username}</b>! {E_CAT_SURPRISED}\n\n{enderia_response}", parse_mode="HTML")
        return
    
    # Обычное сообщение с упоминанием Эндерии
    if should_respond(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        user_bio = await get_user_bio(user_id)
        response = await get_enderia_response(message.text, username, is_reply=False, user_bio=user_bio)
        if response:
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    username = callback.from_user.username or callback.from_user.first_name
    
    if data == "menu_main":
        online, max_players = await get_server_online()
        xp = get_xp(username)
        text = f"{E_HEART} <b>Главное меню</b>\n\n{E_CROWN} Онлайн: {online}/{max_players}\n{E_XP} Твой опыт: {xp} XP\n\n{E_CAT_DANCE} Выбери раздел!"
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
        await callback.answer("Онлайн обновлён!")
    
    elif data == "menu_premium":
        text = f"{E_CROWN} <b>ПРЕМИУМ ДОСТУП</b> {E_CROWN}\n\n{E_MAGIC} <b>Друид</b> - 50₽\n{E_NOTE} <b>Оракул</b> - 100₽\n{E_CROWN} <b>Монарх</b> - 200₽\n{E_RABBIT} <b>Херувим</b> - 300₽ (полёт!)\n{E_HOUSE} <b>Архонт</b> - 400₽\n{E_CAT_DANCE} <b>Серафим</b> - 600₽\n\n{E_HEART} <b>По вопросам:</b> @pelmewki379"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_enderia":
        text = f"{E_HEART} <b>Эндерия - твой живой помощник</b> {E_HEART}\n\n{E_CAT_ROSE} <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n{E_NOTE} <b>Как ко мне обратиться:</b>\nНапиши: Эндер, Эндерия, Энди\n\n{E_JOYSTICK} <b>Игры:</b>\n\"Энди кубик\" - игра в кости\n\"Энди забрать доход\" - собрать опыт с фермы\n\n{E_HOUSE} <b>Ферма:</b>\nОдна ферма, прокачивается до 10 уровня\nКаждый час приносит опыт\n\n{E_MAGIC} <b>Ежедневный бонус 500 XP</b>\nДобавь @lostearth_bot в описание профиля! {E_CAT_ROSE}"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    # ========== ФЕРМА ==========
    elif data == "menu_farm":
        await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМОЙ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farm_keyboard())
        await callback.answer()
    
    elif data == "farm_status":
        farm_info = get_farm_info(username)
        text = f"{E_HOUSE} <b>ТВОЯ ФЕРМА</b> {E_HOUSE}\n\n"
        text += f"📊 Уровень: {farm_info['level']}/10\n"
        text += f"💰 Доход в час: {farm_info['income_per_hour']} XP\n"
        
        if farm_info['upgrading']:
            text += f"⏳ Улучшается до {farm_info['upgrade_complete_level']} уровня\n"
            text += f"🕐 Осталось: {round(farm_info['upgrade_remaining_hours'], 1)} часов\n"
        elif farm_info['next_upgrade']:
            nu = farm_info['next_upgrade']
            text += f"⬆️ Следующий уровень: {nu['level']}\n"
            text += f"💰 Стоимость: {nu['cost']} XP\n"
            text += f"🕐 Время: {nu['hours']} часов\n"
            text += f"📈 Доход станет: {nu['income']} XP/час\n"
        else:
            text += f"🏆 Ферма достигла максимального уровня!\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_farm_keyboard())
        await callback.answer()
    
    elif data == "farm_upgrade":
        farm_info = get_farm_info(username)
        if farm_info['upgrading']:
            await callback.answer(f"Улучшение уже идёт! Осталось {round(farm_info['upgrade_remaining_hours'], 1)} часов", show_alert=True)
        elif farm_info['is_max']:
            await callback.answer("Ферма уже максимального уровня!", show_alert=True)
        else:
            nu = farm_info['next_upgrade']
            success, msg = start_farm_upgrade(username)
            await callback.answer(msg, show_alert=True)
            if success:
                await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМОЙ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farm_keyboard())
    
    elif data == "farm_claim":
        income, hours_passed, farm_info = claim_farm_income(username)
        if income > 0:
            await callback.answer(f"Собрано {income} XP!", show_alert=True)
            await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМОЙ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farm_keyboard())
        else:
            await callback.answer(f"Нет опыта. Подожди ещё {max(0, int(1 - hours_passed))} часа(ов)", show_alert=True)
    
    # ========== ИГРЫ ==========
    elif data == "menu_games":
        xp = get_xp(username)
        text = f"{E_JOYSTICK} <b>ИГРЫ</b> {E_JOYSTICK}\n\n{E_XP} Твой баланс: {xp} XP\n\nВыбери действие:"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_games_keyboard())
        await callback.answer()
    
    elif data == "games_balance":
        xp = get_xp(username)
        await callback.answer(f"Твой баланс: {xp} XP", show_alert=True)
    
    elif data == "games_profile":
        stats = get_stats(username)
        xp = get_xp(username)
        farm_level = get_farm_level(username)
        text = f"{E_CROWN} <b>ПРОФИЛЬ ИГРОКА</b> {E_CROWN}\n\n{E_HOUSE} Имя: {username}\n{E_XP} Опыт: {xp} XP\n{E_JOYSTICK} Побед: {stats['wins']}\n{E_HEART} Поражений: {stats['losses']}\n🏭 Уровень фермы: {farm_level}/10"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "games_daily":
        user_bio = await get_user_bio(callback.from_user.id)
        has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
        
        if not has_bot_in_bio:
            await callback.answer("Добавь @lostearth_bot в описание профиля!", show_alert=True)
        elif can_claim_daily_bonus(username):
            amount = claim_daily_bonus(username)
            xp = get_xp(username)
            await callback.answer(f"+{amount} XP! Твой баланс: {xp} XP", show_alert=True)
        else:
            await callback.answer("Ты уже получал бонус сегодня! Возвращайся завтра!", show_alert=True)
    
    elif data == "games_bet":
        await callback.message.edit_text(f"{E_JOYSTICK} <b>ИГРА В КОСТИ</b> {E_JOYSTICK}\n\n{E_XP} Твой баланс: {get_xp(username)} XP\n\nВыбери ставку:", parse_mode="HTML", reply_markup=get_bet_keyboard())
        await callback.answer()
    
    elif data.startswith("bet_"):
        bet_amount = int(data.replace("bet_", ""))
        xp = get_xp(username)
        
        if bet_amount < 10:
            await callback.answer("Минимальная ставка 10 XP!", show_alert=True)
        elif xp < bet_amount:
            await callback.answer(f"Не хватает XP! У тебя {xp} XP", show_alert=True)
        else:
            await callback.answer(f"Ставка {bet_amount} XP! Играем...", show_alert=False)
            response = await game_dice_bet(username, bot, callback.message.chat.id, bet_amount)
            await callback.message.answer(response, parse_mode="HTML")
            xp_new = get_xp(username)
            text = f"{E_JOYSTICK} <b>ИГРЫ</b> {E_JOYSTICK}\n\n{E_XP} Твой баланс: {xp_new} XP\n\nВыбери действие:"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_games_keyboard())
    
    # ========== ТОП ==========
    elif data == "menu_top":
        leaders = get_leaderboard(10)
        if not leaders:
            text = f"{E_CROWN} Пока нет игроков в топе! Будь первым! {E_MAGIC}"
        else:
            text = f"{E_CROWN} <b>ТОП 10 ИГРОКОВ</b> {E_CROWN}\n\n"
            for i, p in enumerate(leaders, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
                text += f"{medal} {p['username']} - {p['xp']} XP (ферма: {p['farm_level']} ур.)\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"Бот: @{bot_info.username}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
