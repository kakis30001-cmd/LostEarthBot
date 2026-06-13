import asyncio
import os
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
from mcstatus import JavaServer

from enderia import (
    get_enderia_response,
    should_respond,
    set_server_online,
    save_to_log,
    send_spontaneous_message,
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

from database import (
    get_xp,
    update_xp,
    get_stats,
    update_stats,
    get_leaderboard,
    can_claim_daily_bonus,
    claim_daily_bonus,
    create_player,
    init_db,
    get_farm_level,
    update_farm_level,
    get_last_farm,
    update_last_farm,
)

from games import (
    game_dice_bet,
    game_football_bet,
    add_spit,
    collect_farm,
    farm_info,
    upgrade_farm_cmd,
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

# ========== ПРЕМИУМ ЭМОДЗИ ДЛЯ КНОПОК ==========
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
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

BASE_URL = os.getenv("BASE_URL", "https://lostearthbot-production.up.railway.app")
RULES_URL = f"{BASE_URL}/rules.html"
APPLY_URL = f"{BASE_URL}/apply.html"

# Кэш для онлайна
online_cache = {}
last_update = {}
CHAT_ID = None

# ========== MINECRAFT API (через mcstatus) ==========
async def get_server_online():
    """Получение онлайна сервера через mcstatus"""
    global last_update, online_cache
    
    now = datetime.now().timestamp()
    
    # Кэшируем на 30 секунд
    if "online" in last_update and now - last_update["online"] < 30:
        return online_cache.get("online", 0), online_cache.get("max", 0)
    
    try:
        # Подключаемся к серверу
        server = JavaServer.lookup(f"{SERVER['java_ip']}:{SERVER['java_port']}")
        
        # Получаем статус (таймаут 5 секунд)
        status = await server.async_status(timeout=5)
        
        online = status.players.online
        max_players = status.players.max
        
        # Получаем список игроков если есть
        players_list = []
        if status.players.sample:
            players_list = [p.name for p in status.players.sample]
        
        # Получаем MOTD
        motd = status.description
        if isinstance(motd, dict):
            motd = motd.get('text', str(motd))
        
        # Кэшируем
        online_cache["online"] = online
        online_cache["max"] = max_players
        online_cache["players"] = players_list
        online_cache["motd"] = motd
        online_cache["version"] = status.version.name
        
        last_update["online"] = now
        set_server_online(online, max_players)
        
        print(f"✅ Онлайн обновлён: {online}/{max_players} | Игроки: {players_list}")
        return online, max_players
        
    except Exception as e:
        print(f"❌ Ошибка получения онлайна: {e}")
        
        # Если ошибка, возвращаем заглушку
        online_cache["online"] = "?"
        online_cache["max"] = "?"
        last_update["online"] = now
        set_server_online(0, 0)
        return "?", "?"

async def get_server_status_text() -> str:
    """Возвращает красивое сообщение со статусом сервера"""
    online, max_players = await get_server_online()
    
    if online == "?" or online == 0:
        return f"{E_CROWN} <b>СТАТУС СЕРВЕРА</b> {E_CROWN}\n\n🟡 Сервер не отвечает\nПроверьте IP и порт!\n\n💻 Java: <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 Bedrock: <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>"
    
    text = f"{E_CROWN} <b>СТАТУС СЕРВЕРА</b> {E_CROWN}\n\n"
    text += f"🟢 <b>Онлайн:</b> {online}/{max_players}\n"
    
    # Добавляем MOTD если есть
    if "motd" in online_cache and online_cache["motd"]:
        text += f"📝 <b>MOTD:</b> {online_cache['motd']}\n"
    
    # Добавляем версию
    if "version" in online_cache and online_cache["version"]:
        text += f"📦 <b>Версия:</b> {online_cache['version']}\n"
    
    # Добавляем список игроков
    if "players" in online_cache and online_cache["players"]:
        players = online_cache["players"]
        if players:
            text += f"\n👥 <b>Игроки в сети:</b>\n"
            for p in players[:10]:
                text += f"  • {p}\n"
            if len(players) > 10:
                text += f"  • и ещё {len(players) - 10}...\n"
    
    text += f"\n💻 <b>IP Java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>"
    text += f"\n📱 <b>IP Bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>"
    
    return text

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
        [InlineKeyboardButton(text="ФАРМА", callback_data="menu_farm", icon_custom_emoji_id=BUTTON_EMOJI_ID["house"]),
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
    global CHAT_ID
    CHAT_ID = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    await create_player(username)
    
    # Получаем статус сервера
    online, max_players = await get_server_online()
    online_text = f"{online}/{max_players}" if online != "?" else "❓ Нет ответа"
    
    asyncio.create_task(send_spontaneous_message(bot, CHAT_ID))
    
    text = f"""{E_MAGIC} <b>Добро пожаловать на {SERVER['name']}</b> {E_MAGIC}

{E_HOUSE} <b>Мирный режим по заявкам!</b>

{E_CAT_DANCE} <b>Я Энди - твой живой помощник!</b>

{E_CROWN} <b>Текущий онлайн:</b> {online_text}

{E_CROWN} <b>Стартовый баланс: 1000 XP</b>
{E_HEART} <b>Как получить бонус?</b>
Добавь @lostearth_bot в описание профиля!

📝 <b>Команды:</b>
• <b>энди кубик 100</b> - игра в кости
• <b>энди футбол 100</b> - футбол
• <b>энди плюнуть</b> - плюнуть в игрока (30 XP)
• <b>энди фарма</b> - собрать опыт
• <b>энди фарма инфо</b> - инфо о фарме
• <b>энди улучши фарму</b> - улучшить фарму

{E_RABBIT} {E_ANIME} {E_CAT_DANCE}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    text = await get_server_status_text()
    await message.answer(text, parse_mode="HTML")

# ========== ПЛЕВОК ==========
@dp.message(lambda msg: msg.text and msg.text.lower() == "энди плюнуть")
async def spit_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    
    if not message.reply_to_message:
        response = f"{E_CAT_SURPRISED} {username}, в кого плюнуть? Ответь на сообщение игрока и напиши 'энди плюнуть'! {E_HEART}"
        await message.answer(response, parse_mode="HTML")
        return
    
    target = message.reply_to_message.from_user.first_name or message.reply_to_message.from_user.username or "игрок"
    
    if message.reply_to_message.from_user.id == message.from_user.id:
        response = f"{E_CAT_SURPRISED} {username}, ты хочешь плюнуть в себя? Странно... {E_HEART}"
        await message.answer(response, parse_mode="HTML")
        return
    
    success, msg, new_xp = await add_spit(username, target)
    
    if success:
        await message.answer(f"{msg}\n\n{E_CROWN} У тебя осталось {new_xp} XP {E_MAGIC}", parse_mode="HTML")
        
        ai_response = await get_enderia_response(f"{username} плюнул(а) в {target}", username, is_reply=True, game_result=f"Плевок в {target}")
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")
    else:
        await message.answer(f"{E_CAT_SURPRISED} {msg}", parse_mode="HTML")

# ========== ИГРЫ ==========
@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди кубик"))
async def dice_game(message: Message):
    username = message.from_user.username or message.from_user.first_name
    text = message.text.lower()
    
    match = re.search(r"энди кубик\s+(\d+)", text)
    if not match:
        response = f"{E_CAT_DANCE} {username}, напиши ставку! Например: энди кубик 100 {E_JOYSTICK}"
        await message.reply(response, parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    result_text, game_result = await game_dice_bet(username, bet_amount, bot, message.chat.id)
    
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди футбол"))
async def football_game(message: Message):
    username = message.from_user.username or message.from_user.first_name
    text = message.text.lower()
    
    match = re.search(r"энди футбол\s+(\d+)", text)
    if not match:
        response = f"{E_CAT_DANCE} {username}, напиши ставку! Например: энди футбол 100 ⚽"
        await message.reply(response, parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    result_text, game_result = await game_football_bet(username, bet_amount, bot, message.chat.id)
    
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

# ========== ФАРМА ==========
@dp.message(lambda msg: msg.text and msg.text.lower() == "энди фарма")
async def farm_collect_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    result_text, game_result = await collect_farm(username, has_bot_in_bio)
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди фарма инфо")
async def farm_info_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    text = await farm_info(username, has_bot_in_bio)
    await message.answer(text, parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди улучши фарму")
async def farm_upgrade_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_bio = await get_user_bio(message.from_user.id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    result_text, game_result = await upgrade_farm_cmd(username, has_bot_in_bio)
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

# ========== ОСТАЛЬНЫЕ КОМАНДЫ ==========
@dp.message(Command("balance"))
@dp.message(Command("bal"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = await get_xp(username)
    await message.answer(f"{E_CROWN} {username}, твой баланс: {xp} XP! {E_JOYSTICK}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = await get_xp(username)
    stats = await get_stats(username)
    farm_level = await get_farm_level(username)
    
    text = f"""{E_CROWN} <b>ПРОФИЛЬ ИГРОКА</b> {E_CROWN}

{E_HOUSE} Имя: {username}
{E_CROWN} Опыт: {xp} XP
{E_JOYSTICK} Побед: {stats['wins']}
{E_HEART} Поражений: {stats['losses']}
🏭 Уровень фармы: {farm_level}

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

Добавь в описание профиля: @lostearth_bot

📝 <b>Как это сделать:</b>
1. Настройки Telegram → фото профиля
2. Редактировать профиль → Описание
3. Добавь: @lostearth_bot
4. Сохрани и напиши /daily снова! {E_HEART}"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if await can_claim_daily_bonus(username):
        amount = await claim_daily_bonus(username)
        xp = await get_xp(username)
        text = f"{E_MAGIC} <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> {E_MAGIC}\n\n{E_CROWN} +{amount} XP!\n💰 Баланс: {xp} XP\n\n{E_RABBIT} Заходи завтра снова! {E_HEART}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{E_HEART} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {E_CAT_OK}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    leaders = await get_leaderboard(10)
    if not leaders:
        await message.answer(f"{E_CROWN} Пока нет игроков в топе! Будь первым! {E_MAGIC}", parse_mode="HTML")
        return
    
    text = f"{E_CROWN} <b>ТОП ИГРОКОВ ПО ОПЫТУ</b> {E_CROWN}\n\n"
    for i, p in enumerate(leaders, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} <b>{p['username']}</b> - {p['xp']} XP (фарма: {p['farm_level']} ур.)\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{E_JOYSTICK} <b>ДОСТУПНЫЕ КОМАНДЫ</b> {E_JOYSTICK}

🎮 <b>ИГРЫ:</b>
• энди кубик 100 - кости (x2)
• энди футбол 100 - футбол (гол = x2)
• энди плюнуть - плюнуть в игрока (30 XP)

🏭 <b>ФАРМА:</b>
• энди фарма - собрать опыт
• энди фарма инфо - инфо о фарме
• энди улучши фарму - улучшить фарму

📊 <b>ПРОФИЛЬ:</b>
/balance - баланс
/profile - профиль
/daily - бонус 500 XP
/leaderboard - топ игроков

💡 Требование для фармы и бонуса: @lostearth_bot в описании профиля!"""
    await message.answer(text, parse_mode="HTML")

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
@dp.message()
async def handle_message(message: Message):
    global CHAT_ID
    if CHAT_ID is None:
        CHAT_ID = message.chat.id
        asyncio.create_task(send_spontaneous_message(bot, CHAT_ID))
    
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    if user_message.startswith("/"):
        return
    
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
        online_text = f"{online}/{max_players}" if online != "?" else "❓ Нет ответа"
        text = f"{E_HEART} <b>Главное меню</b>\n\n{E_CROWN} Онлайн: {online_text}\n\n{E_CAT_DANCE} /games - все команды"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    
    elif data == "menu_ip":
        text = await get_server_status_text()
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer()
    
    elif data == "refresh_online":
        # Очищаем кэш
        online_cache.clear()
        last_update.clear()
        text = await get_server_status_text()
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer("🔄 Онлайн обновлён!")
    
    elif data == "menu_premium":
        text = f"{E_CROWN} <b>ПРЕМИУМ ДОСТУП</b> {E_CROWN}\n\n{E_MAGIC} <b>Друид</b> - 50₽\n{E_NOTE} <b>Оракул</b> - 100₽\n{E_CROWN} <b>Монарх</b> - 200₽\n{E_RABBIT} <b>Херувим</b> - 300₽\n{E_HOUSE} <b>Архонт</b> - 400₽\n{E_CAT_DANCE} <b>Серафим</b> - 600₽\n\n{E_HEART} <b>По вопросам:</b> @pelmewki379"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_enderia":
        text = f"{E_HEART} <b>Энди - твой помощник</b> {E_HEART}\n\n{E_CAT_DANCE} Напиши 'энди' и я отвечу!\n\n📝 Команды: /games"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_farm":
        await callback.message.edit_text(f"🏭 Напиши 'энди фарма инфо' для информации о фарме", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_top":
        await callback.message.edit_text(f"{E_CROWN} /leaderboard - топ игроков", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    await init_db()
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🤖 Бот: @{bot_info.username}")
    print("✅ Онлайн проверяется через mcstatus")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
