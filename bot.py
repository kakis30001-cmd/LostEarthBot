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

# ========== ПРЕМИУМ ЭМОДЗИ (ВСЕ НОВЫЕ СТИКЕРЫ) ==========
ENDERIA_EMOJI = {
    # Основные
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
    
    # Новые стикеры для ферм и опыта
    "xp": "5258371229777165300",           # опыт
    "spider": "5440875569984052896",        # паук
    "ender": "5440858845381402630",         # Эндермен
    "skeleton": "5440858579093430128",      # скелет
    "zombie": "5440655942536405315",        # зомби
    "creeper": "5440875569984052896",       # крипер
    "cat_rose": "5269347667242162562",      # котик цветы дарит
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# Премиум эмодзи для текста
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

# Эмодзи для ферм (премиум)
E_SPIDER = emoji(ENDERIA_EMOJI["spider"], "🕷️")
E_ENDER = emoji(ENDERIA_EMOJI["ender"], "👾")
E_SKELETON = emoji(ENDERIA_EMOJI["skeleton"], "🏹")
E_ZOMBIE = emoji(ENDERIA_EMOJI["zombie"], "🧟")
E_CREEPER = emoji(ENDERIA_EMOJI["creeper"], "💥")

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
    "heart": "5199427253225667842",
    "magic": "5474144592817318927",
    "xp": "5258371229777165300",
    "spider": "5440875569984052896",
    "ender": "5440858845381402630",
    "skeleton": "5440858579093430128",
    "zombie": "5440655942536405315",
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
         InlineKeyboardButton(text="ЭНДЕРИЯ", callback_data="menu_enderia", icon_custom_emoji_id=BUTTON_EMOJI_ID["cat_ok"])],
        [InlineKeyboardButton(text="ФЕРМЫ", callback_data="menu_farms", icon_custom_emoji_id=BUTTON_EMOJI_ID["spider"]),
         InlineKeyboardButton(text="ИГРЫ", callback_data="menu_games", icon_custom_emoji_id=BUTTON_EMOJI_ID["joystick"])],
        [InlineKeyboardButton(text="ТОП", callback_data="menu_top", icon_custom_emoji_id=BUTTON_EMOJI_ID["crown"])]
    ])

def get_farms_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="МОИ ФЕРМЫ", callback_data="farms_my", icon_custom_emoji_id=BUTTON_EMOJI_ID["house"])],
        [InlineKeyboardButton(text="КУПИТЬ ПАУКОВ (500 XP)", callback_data="buy_farm_пауков", icon_custom_emoji_id=BUTTON_EMOJI_ID["spider"]),
         InlineKeyboardButton(text="КУПИТЬ ЗОМБИ (800 XP)", callback_data="buy_farm_зомби", icon_custom_emoji_id=BUTTON_EMOJI_ID["zombie"])],
        [InlineKeyboardButton(text="КУПИТЬ КРИПЕРОВ (1500 XP)", callback_data="buy_farm_криперов", icon_custom_emoji_id=BUTTON_EMOJI_ID["spider"]),
         InlineKeyboardButton(text="КУПИТЬ СКЕЛЕТОВ (400 XP)", callback_data="buy_farm_скелетов", icon_custom_emoji_id=BUTTON_EMOJI_ID["skeleton"])],
        [InlineKeyboardButton(text="КУПИТЬ ЭНДЕРМЕНОВ (2500 XP)", callback_data="buy_farm_эндерменов", icon_custom_emoji_id=BUTTON_EMOJI_ID["ender"])],
        [InlineKeyboardButton(text="УЛУЧШИТЬ ФЕРМУ", callback_data="farms_upgrade", icon_custom_emoji_id=BUTTON_EMOJI_ID["cat_up"])],
        [InlineKeyboardButton(text="СОБРАТЬ ОПЫТ", callback_data="farms_claim", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"])],
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])]
    ])

def get_upgrade_keyboard(username: str):
    farms = get_farms(username)
    keyboard = []
    for name, data in farms.items():
        level = data.get("level", 1)
        if level < 5:
            cost = UPGRADE_COSTS[level + 1]
            emoji_id = BUTTON_EMOJI_ID.get(name, BUTTON_EMOJI_ID["spider"])
            keyboard.append([InlineKeyboardButton(text=f"{name} (ур.{level} -> {level+1}) - {cost} XP", callback_data=f"upgrade_{name}", icon_custom_emoji_id=emoji_id)])
    if not keyboard:
        keyboard.append([InlineKeyboardButton(text="НЕТ ФЕРМ ДЛЯ УЛУЧШЕНИЯ", callback_data="farms_none")])
    keyboard.append([InlineKeyboardButton(text="НАЗАД", callback_data="menu_farms", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_games_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ИГРА В КОСТИ", callback_data="games_bet", icon_custom_emoji_id=BUTTON_EMOJI_ID["joystick"])],
        [InlineKeyboardButton(text="МОЙ БАЛАНС", callback_data="games_balance", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"])],
        [InlineKeyboardButton(text="МОЙ ПРОФИЛЬ", callback_data="games_profile", icon_custom_emoji_id=BUTTON_EMOJI_ID["crown"])],
        [InlineKeyboardButton(text="ДНЕВНОЙ БОНУС", callback_data="games_daily", icon_custom_emoji_id=BUTTON_EMOJI_ID["magic"])],
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])]
    ])

def get_bet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 XP", callback_data="bet_50", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"]),
         InlineKeyboardButton(text="100 XP", callback_data="bet_100", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"]),
         InlineKeyboardButton(text="200 XP", callback_data="bet_200", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"])],
        [InlineKeyboardButton(text="500 XP", callback_data="bet_500", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"]),
         InlineKeyboardButton(text="1000 XP", callback_data="bet_1000", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"]),
         InlineKeyboardButton(text="5000 XP", callback_data="bet_5000", icon_custom_emoji_id=BUTTON_EMOJI_ID["xp"])],
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_games", icon_custom_emoji_id=BUTTON_EMOJI_ID["back"])]
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
    xp = get_xp(username)
    
    text = f"""{E_MAGIC} <b>Добро пожаловать на {SERVER['name']}</b> {E_MAGIC}

{E_HOUSE} <b>Мирный режим по заявкам!</b>

{E_CAT_ROSE} <b>Я Эндерия - твой живой помощник!</b>

{E_XP} <b>Твой опыт:</b> {xp} XP

{E_HEART} <b>Дневной бонус:</b>
Добавь @lostearth_bot в описание профиля!

{E_CAT_DANCE} {E_RABBIT} {E_ANIME}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

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
        text = f"{E_HEART} <b>Эндерия - твой живой помощник</b> {E_HEART}\n\n{E_CAT_ROSE} <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n{E_NOTE} <b>Как ко мне обратиться:</b>\nНапиши: Эндер, Эндерия, Энди\n\n{E_JOYSTICK} <b>Игры:</b>\n/bet, /balance, /profile, /daily\n\n{E_HOUSE} <b>Фермы:</b>\n/farms, /buy_farm, /upgrade_farm, /claim\n\n{E_MAGIC} <b>Ежедневный бонус 500 XP</b>\nДобавь @lostearth_bot в описание профиля! {E_CAT_ROSE}"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
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
        farms = get_farms(username)
        farm_count = len(farms)
        total_income = calculate_income(farms)
        text = f"{E_CROWN} <b>ПРОФИЛЬ ИГРОКА</b> {E_CROWN}\n\n{E_HOUSE} Имя: {username}\n{E_XP} Опыт: {xp} XP\n{E_JOYSTICK} Побед: {stats['wins']}\n{E_HEART} Поражений: {stats['losses']}\n{E_NOTE} Ферм: {farm_count}\n{E_MAGIC} Доход в час: {total_income} XP"
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
            xp_new = get_xp(username)
            text = f"{E_JOYSTICK} <b>ИГРЫ</b> {E_JOYSTICK}\n\n{E_XP} Твой баланс: {xp_new} XP\n\nВыбери действие:"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_games_keyboard())
    
    # ========== ФЕРМЫ ==========
    elif data == "menu_farms":
        await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМАМИ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farms_keyboard())
        await callback.answer()
    
    elif data == "farms_my":
        farms = get_farms(username)
        if not farms:
            text = f"{E_HOUSE} У тебя пока нет ферм! Купи первую в меню! {E_CAT_ROSE}"
        else:
            text = f"{E_HOUSE} <b>ТВОИ ФЕРМЫ</b> {E_HOUSE}\n\n"
            total_income = 0
            for name, farm_data in farms.items():
                if name == "пауков":
                    icon = E_SPIDER
                elif name == "зомби":
                    icon = E_ZOMBIE
                elif name == "криперов":
                    icon = E_CREEPER
                elif name == "скелетов":
                    icon = E_SKELETON
                elif name == "эндерменов":
                    icon = E_ENDER
                else:
                    icon = E_HOUSE
                base = FARM_BASE.get(name, 50)
                level = farm_data.get("level", 1)
                income = base * level
                total_income += income
                text += f"{icon} {name}: ур. {level} ({income} XP/час)\n"
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
            text += f"{E_XP} Твой опыт: {xp} XP {E_CAT_DANCE}"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_farms_keyboard())
        else:
            farms = get_farms(username)
            if not farms:
                await callback.message.edit_text(f"{E_HOUSE} У тебя нет ферм! Купи первую в меню.", parse_mode="HTML", reply_markup=get_farms_keyboard())
            else:
                await callback.message.edit_text(f"{E_NOTE} Пока не накопилось опыта. Подожди немного или улучшай фермы! {E_CAT_UP}", parse_mode="HTML", reply_markup=get_farms_keyboard())
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
            await callback.message.edit_text(f"{E_HOUSE} <b>УПРАВЛЕНИЕ ФЕРМАМИ</b> {E_HOUSE}\n\nВыбери действие:", parse_mode="HTML", reply_markup=get_farms_keyboard())
    
    # Улучшение ферм через кнопки
    elif data.startswith("upgrade_"):
        farm_key = data.replace("upgrade_", "")
        success, msg = upgrade_farm(username, farm_key)
        await callback.answer(msg, show_alert=True)
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
            text = f"{E_CROWN} Пока нет игроков в топе! Будь первым! {E_MAGIC}"
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
