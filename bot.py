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
    send_spontaneous_message,
    spontaneous_enabled,
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
    spontaneous_messages_list,
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
    connect_db,
    get_farm_level,
    update_farm_level,
    get_last_farm,
    update_last_farm,
    save_chat_message,
    get_chat_history,
    save_user_id,
    check_user_subscribed,
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

# ID администратора
ADMIN_IDS = [8493522297]

# Канал для обязательной подписки
REQUIRED_CHANNEL = "LostEarthSMP"

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
CHAT_ID = None

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

# ========== ПРОВЕРКА УСЛОВИЙ ==========
async def check_all_requirements(user_id: int, username: str) -> tuple[bool, bool, str]:
    """Проверяет все условия для использования бота"""
    # Сохраняем user_id
    await save_user_id(username, user_id)
    
    # Проверка подписки на канал
    is_subscribed = await check_user_subscribed(username, bot, REQUIRED_CHANNEL)
    
    # Проверка описания профиля
    user_bio = await get_user_bio(user_id)
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    # Формируем сообщение о статусе
    status_msg = ""
    if not is_subscribed and not has_bot_in_bio:
        status_msg = "❌ Ты не подписан на канал и нет @lostearth_bot в описании"
    elif not is_subscribed:
        status_msg = "❌ Ты не подписан на канал"
    elif not has_bot_in_bio:
        status_msg = "❌ Нет @lostearth_bot в описании профиля"
    else:
        status_msg = "✅ Все условия выполнены!"
    
    return is_subscribed, has_bot_in_bio, status_msg

async def get_requirements_keyboard():
    """Клавиатура для проверки условий"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ПРОВЕРИТЬ", callback_data="check_requirements")],
        [InlineKeyboardButton(text="📢 КАНАЛ", url="https://t.me/LostEarthSMP")],
        [InlineKeyboardButton(text="❓ КАК ДОБАВИТЬ В ОПИСАНИЕ", callback_data="how_to_add_bio")]
    ])

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

# ========== АДМИН КОМАНДЫ ==========
@dp.message(Command("say"))
async def admin_say(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    text = message.text.replace("/say", "").strip()
    if not text:
        await message.answer("📝 /say <текст>\nпример: /say привет всем", parse_mode="HTML")
        return
    
    await message.answer(f"{E_CAT_DANCE} {text} {E_HEART}", parse_mode="HTML")
    await message.answer("✅ отправлено", parse_mode="HTML")

@dp.message(Command("sayto"))
async def admin_say_to(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("📝 /sayto <chat_id> <текст>", parse_mode="HTML")
        return
    
    try:
        chat_id = int(parts[1])
        text = parts[2]
        await bot.send_message(chat_id, f"{E_CAT_DANCE} {text} {E_HEART}", parse_mode="HTML")
        await message.answer(f"✅ отправлено в {chat_id}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ ошибка: {e}", parse_mode="HTML")

@dp.message(Command("test_spontaneous"))
async def test_spontaneous(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    msg = random.choice(spontaneous_messages_list)
    await message.answer(f"{E_CAT_DANCE} 🧪 ТЕСТ: {msg} {E_HEART}", parse_mode="HTML")

@dp.message(Command("spontaneous"))
async def toggle_spontaneous(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    global spontaneous_enabled
    spontaneous_enabled = not spontaneous_enabled
    status = "включены" if spontaneous_enabled else "выключены"
    await message.answer(f"✅ спонтанные сообщения {status}", parse_mode="HTML")

@dp.message(Command("chatlog"))
async def chat_log(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    try:
        with open("chat.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-30:]
            log_text = "".join(last_lines)
            if len(log_text) > 4000:
                log_text = log_text[-4000:]
            await message.answer(f"📋 последние сообщения:\n<code>{log_text}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ ошибка: {e}", parse_mode="HTML")

@dp.message(Command("clear_all_memory"))
async def clear_all_memory(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ у тебя нет прав", parse_mode="HTML")
        return
    
    from enderia import user_memory, user_greeted
    user_memory.clear()
    user_greeted.clear()
    await message.answer("✅ память всех очищена", parse_mode="HTML")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    await create_player(username)
    await save_user_id(username, user_id)
    online, max_players = await get_server_online()
    
    asyncio.create_task(send_spontaneous_message(bot, CHAT_ID))
    
    # Проверяем условия
    is_subscribed, has_bot_in_bio, status = await check_all_requirements(user_id, username)
    
    text = f"""{E_MAGIC} <b>добро пожаловать на {SERVER['name']}</b> {E_MAGIC}

{E_HOUSE} <b>мирный режим по заявкам</b>

{E_CAT_DANCE} <b>я энди - твой живой помощник</b>

{E_CROWN} <b>текущий онлайн:</b> {online}/{max_players}

{E_CROWN} <b>стартовый баланс: 1000 xp</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>⚡ ДЛЯ ИСПОЛЬЗОВАНИЯ БОТА:</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>Подпишись на канал:</b>
👉 https://t.me/LostEarthSMP

2️⃣ <b>Добавь в описание профиля:</b>
👉 @lostearth_bot

📝 <b>как добавить в описание?</b>
• настройки telegram → фото профиля
• редактировать профиль → описание
• добавь: @lostearth_bot
• сохрани

{status}

{E_RABBIT} {E_ANIME} {E_CAT_DANCE}"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=await get_requirements_keyboard())

@dp.message(Command("check"))
async def check_cmd(message: Message):
    """Проверить все условия"""
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    is_subscribed, has_bot_in_bio, status = await check_all_requirements(user_id, username)
    
    text = f"""📋 <b>ПРОВЕРКА УСЛОВИЙ</b>

1️⃣ <b>Подписка на канал</b> @LostEarthSMP:
{'✅ ПОДПИСАН' if is_subscribed else '❌ НЕ ПОДПИСАН'}

2️⃣ <b>Описание профиля</b> (@lostearth_bot):
{'✅ НАЙДЕН' if has_bot_in_bio else '❌ НЕ НАЙДЕН'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>СТАТУС:</b> {status}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{'🎉 Все условия выполнены! Фарма и бонусы работают 💜' if is_subscribed and has_bot_in_bio else '⚠️ Выполни все условия выше и нажми /check снова'}"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=await get_requirements_keyboard())

@dp.message(Command("howto"))
async def howto_cmd(message: Message):
    """Инструкция как добавить бота в описание"""
    text = f"""📖 <b>КАК ДОБАВИТЬ @lostearth_bot В ОПИСАНИЕ ПРОФИЛЯ</b>

<b>ШАГ 1:</b> Открой настройки Telegram
• iOS: Настройки → Редактировать профиль
• Android: Настройки → Нажать на фото/имя
• PC: Настройки → Редактировать профиль

<b>ШАГ 2:</b> Найди поле "Описание" (Bio)

<b>ШАГ 3:</b> Впиши туда:
<code>@lostearth_bot</code>

<b>ШАГ 4:</b> Нажми "Сохранить"

<b>ШАГ 5:</b> Вернись в бот и напиши /check

⚠️ <b>ВАЖНО:</b> Описание проверяется автоматически!
Если добавил, но бот не видит - подожди 1-2 минуты и напиши /check снова

💡 <b>СОВЕТ:</b> Можешь добавить что-то ещё в описание, главное чтобы был <b>@lostearth_bot</b>

{E_HEART} После выполнения всех условий фарма и бонусы заработают!"""
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = await get_xp(username)
    await message.answer(f"{E_CROWN} {username}, твой баланс: {xp} xp {E_JOYSTICK}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    xp = await get_xp(username)
    stats = await get_stats(username)
    farm_level = await get_farm_level(username)
    
    text = f"""{E_CROWN} <b>профиль игрока</b> {E_CROWN}

{E_HOUSE} имя: {username}
{E_CROWN} опыт: {xp} xp
{E_JOYSTICK} побед: {stats['wins']}
{E_HEART} поражений: {stats['losses']}
🏭 уровень фармы: {farm_level}

{E_MAGIC} <b>ежедневный бонус: +500 xp</b>
{E_NOTE} добавь в описание: @lostearth_bot

{E_CAT_OK} /daily - получить бонус {E_HEART}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    # Проверяем условия
    is_subscribed, has_bot_in_bio, status = await check_all_requirements(user_id, username)
    
    if not is_subscribed or not has_bot_in_bio:
        text = f"""{E_CAT_SURPRISED} <b>НЕТ БОНУСА</b> {E_CAT_SURPRISED}

<b>Чтобы получать бонусы:</b>

1️⃣ {'✅' if is_subscribed else '❌'} <b>Подписка на канал:</b> @LostEarthSMP
2️⃣ {'✅' if has_bot_in_bio else '❌'} <b>В описании профиля:</b> @lostearth_bot

<b>📝 Как исправить:</b>
• Подпишись: https://t.me/LostEarthSMP
• Добавь в описание: @lostearth_bot
• Напиши /check для проверки"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if await can_claim_daily_bonus(username):
        amount = await claim_daily_bonus(username)
        xp = await get_xp(username)
        text = f"{E_MAGIC} <b>ежедневный бонус</b> {E_MAGIC}\n\n{E_CROWN} +{amount} xp\n💰 баланс: {xp} xp\n\n{E_RABBIT} заходи завтра снова {E_HEART}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{E_HEART} {username}, ты уже получал бонус сегодня возвращайся завтра {E_CAT_OK}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    leaders = await get_leaderboard(10)
    if not leaders:
        await message.answer(f"{E_CROWN} пока нет игроков в топе будь первым {E_MAGIC}", parse_mode="HTML")
        return
    
    text = f"{E_CROWN} <b>топ игроков по опыту</b> {E_CROWN}\n\n"
    for i, p in enumerate(leaders, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} <b>{p['username']}</b> - {p['xp']} xp (фарма: {p['farm_level']} ур)\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"{E_CROWN} <b>онлайн: {online}/{max_players}</b> {E_CAT_DANCE}", parse_mode="HTML")

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{E_JOYSTICK} <b>доступные команды</b> {E_JOYSTICK}

🎮 <b>игры:</b>
• энди кубик 100 - кости (x2)
• энди футбол 100 - футбол (гол = x2)
• энди плюнуть - плюнуть в игрока (30 xp)

🏭 <b>фарма:</b>
• энди фарма - собрать опыт
• энди фарма инфо - инфо о фарме
• энди улучши фарму - улучшить фарму

📊 <b>профиль:</b>
/balance - баланс
/profile - профиль
/daily - бонус 500 xp
/leaderboard - топ игроков
/check - проверить условия

💡 <b>требование для фармы и бонуса:</b>
• Подписка: @LostEarthSMP
• @lostearth_bot в описании профиля"""
    await message.answer(text, parse_mode="HTML")

# ========== ПЛЕВОК ==========
@dp.message(lambda msg: msg.text and msg.text.lower() == "энди плюнуть")
async def spit_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    
    if not message.reply_to_message:
        await message.answer(f"{E_CAT_SURPRISED} в кого плюнуть? ответь на сообщение игрока и напиши 'энди плюнуть' {E_HEART}", parse_mode="HTML")
        return
    
    target = message.reply_to_message.from_user.first_name or message.reply_to_message.from_user.username or "игрок"
    
    if message.reply_to_message.from_user.id == message.from_user.id:
        await message.answer(f"{E_CAT_SURPRISED} ты хочешь плюнуть в себя? странно... {E_HEART}", parse_mode="HTML")
        return
    
    success, msg, new_xp = await add_spit(username, target)
    
    if success:
        await message.answer(f"{msg}\n\n{E_CROWN} у тебя осталось {new_xp} xp {E_MAGIC}", parse_mode="HTML")
        
        ai_response = await get_enderia_response(f"{username} плюнул в {target}", username, is_reply=True, game_result=f"плевок в {target}")
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
        await message.reply(f"{E_CAT_DANCE} напиши ставку например: энди кубик 100 {E_JOYSTICK}", parse_mode="HTML")
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
        await message.reply(f"{E_CAT_DANCE} напиши ставку например: энди футбол 100 ⚽", parse_mode="HTML")
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
    user_id = message.from_user.id
    
    # Проверяем условия
    is_subscribed, has_bot_in_bio, _ = await check_all_requirements(user_id, username)
    
    result_text, game_result = await collect_farm(username, has_bot_in_bio, is_subscribed)
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди фарма инфо")
async def farm_info_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    # Проверяем условия
    is_subscribed, has_bot_in_bio, _ = await check_all_requirements(user_id, username)
    
    text = await farm_info(username, has_bot_in_bio, is_subscribed)
    await message.answer(text, parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди улучши фарму")
async def farm_upgrade_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    # Проверяем условия
    is_subscribed, has_bot_in_bio, _ = await check_all_requirements(user_id, username)
    
    result_text, game_result = await upgrade_farm_cmd(username, has_bot_in_bio, is_subscribed)
    await message.answer(result_text, parse_mode="HTML")
    
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response:
            await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

# ========== ОБРАБОТЧИК ==========
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
        text = f"{E_HEART} <b>главное меню</b>\n\n{E_CROWN} онлайн: {online}/{max_players}\n\n{E_CAT_DANCE} /games - все команды"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        text = f"{E_CROWN} <b>lostearth</b> {E_CROWN}\n\n{E_HOUSE} <b>java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>приятной игры</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer()
    
    elif data == "refresh_online":
        online_cache.clear()
        last_update.clear()
        online, max_players = await get_server_online()
        text = f"{E_CROWN} <b>lostearth</b> {E_CROWN}\n\n{E_HOUSE} <b>java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>приятной игры</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer("онлайн обновлён")
    
    elif data == "menu_premium":
        text = f"{E_CROWN} <b>премиум доступ</b> {E_CROWN}\n\n{E_MAGIC} <b>друид</b> - 50₽\n{E_NOTE} <b>оракул</b> - 100₽\n{E_CROWN} <b>монарх</b> - 200₽\n{E_RABBIT} <b>херувим</b> - 300₽\n{E_HOUSE} <b>архонт</b> - 400₽\n{E_CAT_DANCE} <b>серафим</b> - 600₽\n\n{E_HEART} <b>по вопросам:</b> @pelmewki379"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_enderia":
        text = f"{E_HEART} <b>энди - твой помощник</b> {E_HEART}\n\n{E_CAT_DANCE} напиши 'энди' и я отвечу\n\n📝 команды: /games"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_farm":
        await callback.message.edit_text(f"{E_HOUSE} напиши 'энди фарма инфо' для информации о фарме", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "menu_top":
        await callback.message.edit_text(f"{E_CROWN} /leaderboard - топ игроков", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    
    elif data == "check_requirements":
        user_id = callback.from_user.id
        username = callback.from_user.username or callback.from_user.first_name
        is_subscribed, has_bot_in_bio, status = await check_all_requirements(user_id, username)
        
        text = f"""📋 <b>ПРОВЕРКА УСЛОВИЙ
