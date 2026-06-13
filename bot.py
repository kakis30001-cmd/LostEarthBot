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
    FARMS,
    UPGRADE_COSTS,
    FARM_EMOJI,
    FARM_BASE,
    FARM_COST,
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
        [InlineKeyboardButton(text="🖥️ IP И ОНЛАЙН", callback_data="menu_ip")],
        [InlineKeyboardButton(text="📜 ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL)),
         InlineKeyboardButton(text="📝 ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL))],
        [InlineKeyboardButton(text="👑 ПРЕМИУМ", callback_data="menu_premium"),
         InlineKeyboardButton(text="💜 ЭНДЕРИЯ", callback_data="menu_enderia")],
        [InlineKeyboardButton(text="🏭 ФЕРМЫ", callback_data="menu_farms"),
         InlineKeyboardButton(text="🎮 ИГРЫ", callback_data="menu_games")],
        [InlineKeyboardButton(text="🏆 ТОП", callback_data="menu_top")]
    ])

def get_farms_keyboard():
    """Клавиатура для управления фермами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 МОИ ФЕРМЫ", callback_data="farms_my")],
        [InlineKeyboardButton(text="🕷️ КУПИТЬ ПАУКОВ (500 XP)", callback_data="buy_farm_пауков"),
         InlineKeyboardButton(text="🧟 КУПИТЬ ЗОМБИ (800 XP)", callback_data="buy_farm_зомби")],
        [InlineKeyboardButton(text="💥 КУПИТЬ КРИПЕРОВ (1500 XP)", callback_data="buy_farm_криперов"),
         InlineKeyboardButton(text="🏹 КУПИТЬ СКЕЛЕТОВ (400 XP)", callback_data="buy_farm_скелетов")],
        [InlineKeyboardButton(text="👾 КУПИТЬ ЭНДЕРМЕНОВ (2500 XP)", callback_data="buy_farm_эндерменов")],
        [InlineKeyboardButton(text="⬆️ УЛУЧШИТЬ ФЕРМУ", callback_data="farms_upgrade")],
        [InlineKeyboardButton(text="💰 СОБРАТЬ ОПЫТ", callback_data="farms_claim")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

def get_upgrade_keyboard(username: str):
    """Клавиатура для выбора фермы на улучшение"""
    farms = get_farms(username)
    keyboard = []
    for name, data in farms.items():
        level = data.get("level", 1)
        if level < 5:
            cost = UPGRADE_COSTS[level + 1]
            emoji_farm = FARM_EMOJI.get(name, "🏭")
            keyboard.append([InlineKeyboardButton(text=f"{emoji_farm} {name} (ур.{level} -> {level+1}) - {cost} XP", callback_data=f"upgrade_{name}")])
    if not keyboard:
        keyboard.append([InlineKeyboardButton(text="❌ НЕТ ФЕРМ ДЛЯ УЛУЧШЕНИЯ", callback_data="farms_none")])
    keyboard.append([InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_farms")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_games_keyboard():
    """Клавиатура для игр"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 ИГРА В КОСТИ", callback_data="games_bet")],
        [InlineKeyboardButton(text="💰 МОЙ БАЛАНС", callback_data="games_balance")],
        [InlineKeyboardButton(text="👤 МОЙ ПРОФИЛЬ", callback_data="games_profile")],
        [InlineKeyboardButton(text="🎁 ДНЕВНОЙ БОНУС", callback_data="games_daily")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main")]
    ])

def get_bet_keyboard():
    """Клавиатура для ставок в кости"""
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

{E_CAT_DANCE} <b>Я Эндерия - твой живой помощник!</b>

{E_CROWN} <b>Текущий онлайн:</b> {online}/{max_players}
{E_CROWN} <b>Твой опыт:</b> {xp} XP

{E_HEART} <b>Дневной бонус:</b>
Добавь @lostearth_bot в описание профиля!

🐰💜🐱"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{E_CROWN} <b>Онлайн: {online}/{max_players}</b> {E_CAT_DANCE}", parse_mode="HTML")

# ========== ОБРАБОТЧИК ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    if user_message.startswith("/"):
        return
    
    if should_respond(user_message):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        user_bio = await get_user_bio(message.from_user.id)
        response = await get_enderia_response(user_message, username, is_reply=False, user_bio=user_bio)
        if response:
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    username = callback.from_user.username or callback.from_user.first_name
    
    # ========== ГЛАВНОЕ МЕНЮ ==========
    if data == "menu_main":
        online, max_players = await get_server_online()
        xp = get_xp(username)
        text = f"{E_HEART} <b>Главное меню</b>\n\n{E_CROWN} Онлайн: {online}/{max_players}\n{E_CROWN} Твой опыт: {xp} XP\n\n{E_CAT_DANCE} Выбери раздел!"
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
        text = f"{E_HEART} <b>Эндерия - твой живой помощник</b> {E_HEART}\n\n{E_CAT_DANCE} <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n{E_NOTE} <b>Как ко мне обратиться:</b>\nНапиши: Эндер, Эндерия, Энди\n\n{E_JOYSTICK} <b>Игры:</b>\n/bet, /balance, /profile, /daily\n\n{E_HOUSE} <b>Фермы:</b>\n/farms, /buy_farm, /upgrade_farm, /claim\n\n{E_MAGIC} <b>Ежедневный бонус 500 XP</b>\nДобавь @lostearth_bot в описание профиля!"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    # ========== ИГРЫ ==========
    elif data == "menu_games":
        xp = get_xp(username)
        text = f"{E_JOYSTICK} <b>ИГРЫ</b> {E_JOYSTICK}\n\n{E_CROWN} Твой баланс: {xp} XP\n\nВыбери действие:"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_games_keyboard())
        await callback.answer()
    
    elif data == "games_balance":
        xp = get_xp(username)
        await callback.answer(f"Твой баланс: {xp} XP", show_alert=True)
    
    elif data == "games_profile":
        stats = get_stats(username)
        xp = get_xp(username)
        farms = get_farms(username)
        farm_count = len(farms)
        total_income = calculate_income(farms)
        text = f"{E_CROWN} <b>ПРОФИЛЬ ИГРОКА</b> {E_CROWN}\n\n{E_HOUSE} Имя: {username}\n{E_CROWN} Опыт: {xp} XP\n{E_JOYSTICK} Побед: {stats['wins']}\n{E_HEART} Поражений: {stats['losses']}\n{E_NOTE} Ферм: {farm_count}\n{E_MAGIC} Доход в час: {total_income} XP"
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
        await callback.message.edit_text(f"{E_JOYSTICK} <b>ИГРА В КОСТИ</b> {E_JOYSTICK}\n\n{E_CROWN} Твой баланс: {get_xp(username)} XP\n\nВыбери ставку:", parse_mode="HTML", reply_markup=get_bet_keyboard())
        await callback.answer()
    
    # Ставки
    elif data.startswith("bet_"):
        bet_amount = int(data.replace("bet_", ""))
        xp = get_xp(username)
        
        if bet_amount < 50:
            await callback.answer("Минимальная ставка 50 XP!", show_alert=True)
        elif xp < bet_amount:
            await callback.answer(f"Не хватает XP! У тебя {xp} XP", show_alert=True)
        else:
            await callback.answer(f"Ставка {bet_amount} XP! Играем...", show_alert=False)
            response = await game_dice_bet(username, bet_amount, bot, callback.message.chat.id)
            await callback.message.answer(response, parse_mode="HTML")
            # Обновляем меню игр
            xp_new = get_xp(username)
            text = f"{E_JOYSTICK} <b>ИГРЫ</b> {E_JOYSTICK}\n\n{E_CROWN} Твой баланс: {xp_new} XP\n\nВыбери действие:"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_games_keyboard())
    
    # ========== ФЕРМЫ ==========
    elif data == "menu_farms":
        await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМАМИ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farms_keyboard())
        await callback.answer()
    
    elif data == "farms_my":
        farms = get_farms(username)
        if not farms:
            text = f"{E_HOUSE} У тебя пока нет ферм! Купи первую в меню!"
        else:
            text = f"{E_HOUSE} <b>ТВОИ ФЕРМЫ</b> {E_HOUSE}\n\n"
            total_income = 0
            for name, farm_data in farms.items():
                emoji_farm = FARM_EMOJI.get(name, "🏭")
                base = FARM_BASE.get(name, 50)
                level = farm_data.get("level", 1)
                income = base * level
                total_income += income
                text += f"{emoji_farm} {name}: ур. {level} ({income} XP/час)\n"
            text += f"\n{E_CROWN} Общий доход: {total_income} XP/час"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_farms_keyboard())
        await callback.answer()
    
    elif data == "farms_upgrade":
        farms = get_farms(username)
        if not farms:
            await callback.message.edit_text(f"{E_HOUSE} У тебя нет ферм для улучшения! Купи сначала.", parse_mode="HTML", reply_markup=get_farms_keyboard())
        else:
            await callback.message.edit_text(f"{E_CAT_UP} <b>ВЫБЕРИ ФЕРМУ ДЛЯ УЛУЧШЕНИЯ</b> {E_CAT_UP}", parse_mode="HTML", reply_markup=get_upgrade_keyboard(username))
        await callback.answer()
    
    elif data == "farms_claim":
        result = claim_income(username)
        if isinstance(result, tuple):
            income, details = result
        else:
            income = result
            details = []
        
        if income > 0:
            xp = get_xp(username)
            text = f"{E_MAGIC} <b>Собрано {income} XP</b> с ферм! {E_MAGIC}\n\n"
            if details:
                text += "\n".join(details) + "\n\n"
            text += f"{E_CROWN} Твой опыт: {xp} XP"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_farms_keyboard())
        else:
            farms = get_farms(username)
            if not farms:
                await callback.message.edit_text(f"{E_HOUSE} У тебя нет ферм! Купи первую в меню.", parse_mode="HTML", reply_markup=get_farms_keyboard())
            else:
                await callback.message.edit_text(f"{E_NOTE} Пока не накопилось опыта. Подожди немного или улучшай фермы!", parse_mode="HTML", reply_markup=get_farms_keyboard())
        await callback.answer()
    
    # Покупка ферм через кнопки
    elif data.startswith("buy_farm_"):
        farm_key = data.replace("buy_farm_", "")
        farm_map_display = {
            "пауков": "пауков", "зомби": "зомби", "криперов": "криперов", "скелетов": "скелетов", "эндерменов": "эндерменов"
        }
        if farm_key in farm_map_display:
            success, msg = buy_farm(username, farm_map_display[farm_key])
            await callback.answer(msg, show_alert=True)
            # Обновляем меню ферм
            await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМАМИ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farms_keyboard())
    
    # Улучшение ферм через кнопки
    elif data.startswith("upgrade_"):
        farm_key = data.replace("upgrade_", "")
        success, msg = upgrade_farm(username, farm_key)
        await callback.answer(msg, show_alert=True)
        # Возвращаем в меню выбора улучшения
        farms = get_farms(username)
        if farms:
            await callback.message.edit_text(f"{E_CAT_UP} <b>ВЫБЕРИ ФЕРМУ ДЛЯ УЛУЧШЕНИЯ</b> {E_CAT_UP}", parse_mode="HTML", reply_markup=get_upgrade_keyboard(username))
        else:
            await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМАМИ</b> {E_HOUSE}", parse_mode="HTML", reply_markup=get_farms_keyboard())
    
    elif data == "farms_none":
        await callback.answer("У тебя нет ферм для улучшения! Купи сначала ферму.", show_alert=True)
    
    # ========== ТОП ==========
    elif data == "menu_top":
        leaders = get_leaderboard(10)
        if not leaders:
            text = f"{E_CROWN} Пока нет игроков в топе! Будь первым!"
        else:
            text = f"{E_CROWN} <b>ТОП 10 ИГРОКОВ</b> {E_CROWN}\n\n"
            for i, p in enumerate(leaders, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
                text += f"{medal} {p['username']} - {p['xp']} XP (ферм: {p['farms_count']})\n"
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
