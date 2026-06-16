import asyncio
import os
import re
from datetime import datetime
from threading import Thread
import random
import urllib.parse
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from mcstatus import JavaServer

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
    current_online,
    current_max,
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
)

from games import (
    add_spit,
    farm_info,
    collect_farm,
    upgrade_farm_cmd,
    game_dice_bet,
    game_football_bet,
    game_slots_bet,
)

# ========== ИГРА БУНКЕР ==========
from bunker_game import BunkerGame, GameState, BunkerPlayer

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = -1003891930776

ADMIN_IDS = [8493522297]

# Фоновая задача для обновления онлайна
async def update_online_loop():
    while True:
        try:
            online, max_players = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
            set_server_online(online, max_players)
        except Exception as e:
            print(f"Ошибка в цикле обновления онлайна: {e}")
        
        await asyncio.sleep(60)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
online_cache = {}
last_update = {}
CHAT_ID = None
active_players = set()

# Хранилища для игры Бункер
bunker_lobbies: Dict[int, BunkerGame] = {}
active_bunker_games: Dict[int, BunkerGame] = {}

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

@app.route('/donate')
def serve_donate():
    return send_from_directory('static', 'donate.html')

@app.route('/donate.html')
def serve_donate_html():
    return send_from_directory('static', 'donate.html')

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

# ========== MINECRAFT API ==========
async def get_java_status(ip: str, port: int = 25565) -> tuple:
    try:
        print(f"🔍 [DEBUG] Пытаюсь опросить {ip}:{port}...")
        server = JavaServer(ip, port)
        status = await server.async_status(tries=3)
        online = status.players.online
        max_players = status.players.max
        print(f"✅ [DEBUG] Сервер ответил: {online}/{max_players} игроков")
        return online, max_players
    except Exception as e:
        print(f"❌ [DEBUG] Ошибка подключения: {e}")
        return 0, 0

async def get_server_online():
    return current_online, current_max

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="IP И ОНЛАЙН", callback_data="menu_ip")],
        [InlineKeyboardButton(text="ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL)),
         InlineKeyboardButton(text="ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL))],
        [InlineKeyboardButton(text="ПРЕМИУМ", callback_data="menu_premium"),
         InlineKeyboardButton(text="ЭНДИ", callback_data="menu_enderia")],
        [InlineKeyboardButton(text="ФАРМА", callback_data="menu_farm"),
         InlineKeyboardButton(text="ТОП", callback_data="menu_top")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="НАЗАД", callback_data="menu_main")]
    ])

# ========== АДМИН КОМАНДЫ ==========
@dp.message(Command("say"))
async def admin_say(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    text = message.text.replace("/say", "").strip()
    if not text:
        return await message.answer("📝 /say <текст>\nпример: /say привет всем", parse_mode="HTML")
    await message.answer(f"{E_CAT_DANCE} {text} {E_HEART}", parse_mode="HTML")

@dp.message(Command("imagine"))
async def admin_imagine(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    
    prompt = message.text.replace("/imagine", "").strip()
    if not prompt:
        return await message.answer(
            "📝 <b>Как использовать:</b> <code>/imagine <описание></code>\n"
            "💡 <i>Пример: /imagine красивый замок в майнкрафт, шейдеры, 4k</i>", 
            parse_mode="HTML"
        )
    
    wait_msg = await message.answer(f"{E_MAGIC} Энди рисует, подожди немного...", parse_mode="HTML")
    
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        await bot.send_photo(
            chat_id=message.chat.id, 
            photo=image_url, 
            caption=f"{E_MAGIC} <b>Твой арт:</b> {prompt}",
            parse_mode="HTML"
        )
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text(f"❌ <b>Ошибка генерации:</b> {e}", parse_mode="HTML")

@dp.message(Command("sayto"))
async def admin_say_to(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("📝 /sayto <chat_id> <текст>", parse_mode="HTML")
    try:
        await bot.send_message(int(parts[1]), f"{E_CAT_DANCE} {parts[2]} {E_HEART}", parse_mode="HTML")
        await message.answer(f"✅ отправлено в {parts[1]}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ ошибка: {e}", parse_mode="HTML")

@dp.message(Command("givexp"))
async def admin_give_xp(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "📝 <b>Использование:</b> <code>/givexp <имя_игрока> <сумма></code>\n"
            "💡 <i>Пример: /givexp Steve 5000</i>", 
            parse_mode="HTML"
        )
    
    target_username = parts[1]
    try:
        amount = int(parts[2])
    except ValueError:
        return await message.answer("❌ Сумма должна быть целым числом!", parse_mode="HTML")
    
    await update_xp(target_username, amount)
    new_xp = await get_xp(target_username)
    action = "Выдано" if amount > 0 else "Списано"
    
    await message.answer(
        f"{E_MAGIC} <b>Успешно!</b>\n\n"
        f"👤 <b>Игрок:</b> {target_username}\n"
        f"💰 <b>{action}:</b> {abs(amount)} xp\n"
        f"🏦 <b>Новый баланс:</b> {new_xp} xp", 
        parse_mode="HTML"
    )

@dp.message(Command("spontaneous"))
async def toggle_spontaneous(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    global spontaneous_enabled
    spontaneous_enabled = not spontaneous_enabled
    await message.answer(f"✅ спонтанные сообщения {'включены' if spontaneous_enabled else 'выключены'}", parse_mode="HTML")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    
    username = message.from_user.username or message.from_user.first_name
    await create_player(username)
    
    # Проверяем, запущен ли бот через кнопку "ЗАЙТИ В БОТА"
    if message.text and "bunker" in message.text:
        user_id = message.from_user.id
        
        # Ищем активную игру для этого пользователя
        for game in active_bunker_games.values():
            if user_id in game.players and game.state == GameState.CHARACTERS_GENERATED:
                await game.start_reveal_phase()
                await message.answer(
                    f"{E_MAGIC} <b>добро пожаловать в бункер!</b>\n\n"
                    f"<i>выбери характеристику для раскрытия в этом раунде</i>",
                    parse_mode="HTML"
                )
                return
        
        await message.answer(
            f"{E_MAGIC} <b>привет, я энди</b> {E_MAGIC}\n\n"
            f"{E_CAT_DANCE} я твой текстовый помощник!\n\n"
            f"{E_HEART} <b>что я умею:</b>\n"
            f"📝 рассказывать информацию о сервере\n"
            f"🎮 играть с тобой в игры\n"
            f"🏭 помогать с фермой\n"
            f"📊 показывать профиль\n\n"
            f"{E_CROWN} <b>стартовый баланс: 1000 xp</b>\n\n"
            f"{E_CAT_DANCE} я всегда рядом, телепортнусь по первому зову! {E_HEART}",
            parse_mode="HTML"
        )
        return
    
    # Обычный /start
    text = f"""{E_MAGIC} <b>привет, я энди</b> {E_MAGIC}

{E_CAT_DANCE} я твой текстовый помощник!

{E_HEART} <b>что я умею:</b>

📝 <b>рассказывать информацию:</b>
• про сервер lostearth (ip, режимы, правила)
• про донаты и премиум
• про онлайн на сервере

🎮 <b>играть с тобой:</b>
• энди кубик 100 — кости
• энди футбол 100 — футбол
• энди слоты 100 — слоты
• энди плюнуть — плюнуть в игрока

🏭 <b>помогать с фермой:</b>
• энди фарма — собрать опыт
• энди фарма инфо — инфо о ферме
• энди улучши фарму — улучшить ферму

📊 <b>показывать профиль:</b>
• /balance — баланс xp
• /profile — профиль
• /daily — бонус 500 xp
• /top — топ игроков

{E_CROWN} <b>стартовый баланс: 1000 xp</b>

{E_RABBIT} <b>просто спроси меня:</b>
• "энди список команд"
• "энди какой айпи"
• "энди сколько онлайна"
• "энди расскажи про донаты"

{E_CAT_DANCE} я всегда рядом, телепортнусь по первому зову! {E_HEART}"""
    
    await message.answer(text, parse_mode="HTML")
    asyncio.create_task(send_spontaneous_message(bot, CHAT_ID))

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

{E_CAT_OK} /daily - получить бонус {E_HEART}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    if await can_claim_daily_bonus(username):
        amount = await claim_daily_bonus(username)
        xp = await get_xp(username)
        await message.answer(f"{E_MAGIC} <b>ежедневный бонус</b> {E_MAGIC}\n\n{E_CROWN} +{amount} xp\n💰 баланс: {xp} xp\n\n{E_RABBIT} заходи завтра снова {E_HEART}", parse_mode="HTML")
    else:
        await message.answer(f"{E_HEART} {username}, ты уже получал бонус сегодня возвращайся завтра {E_CAT_OK}", parse_mode="HTML")

@dp.message(Command("leaderboard"))
@dp.message(Command("top"))
async def leaderboard_cmd(message: Message):
    leaders = await get_leaderboard(10)
    if not leaders:
        return await message.answer(f"{E_CROWN} пока нет игроков в топе будь первым {E_MAGIC}", parse_mode="HTML")
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
• энди слоты 100 - слоты
• энди плюнуть - плюнуть в игрока (30 xp)

🏭 <b>фарма:</b>
• энди фарма - собрать опыт
• энди фарма инфо - инфо о фарме
• энди улучши фарму - улучшить фарму

📊 <b>профиль:</b>
/balance - баланс
/profile - профиль
/daily - бонус 500 xp
/leaderboard - топ игроков"""
    await message.answer(text, parse_mode="HTML")

# ========== ПЕРЕВОД XP ==========
@dp.message(lambda msg: msg.text and msg.text.lower().startswith("пай "))
async def pay_cmd(message: Message):
    if not message.reply_to_message:
        return await message.answer(f"{E_CAT_SURPRISED} ответь на сообщение игрока, которому хочешь перевести xp!", parse_mode="HTML")
    
    match = re.search(r"пай\s+(\d+)", message.text.lower())
    if not match:
        return await message.answer(f"{E_CAT_DANCE} напиши сумму, например: пай 100", parse_mode="HTML")
        
    amount = int(match.group(1))
    if amount <= 0 or amount > 5000:
        return await message.answer(f"{E_CAT_SURPRISED} можно перевести от 1 до 5000 xp за раз!", parse_mode="HTML")
        
    sender = message.from_user.username or message.from_user.first_name
    target = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    
    if sender == target:
        return await message.answer(f"{E_CAT_SURPRISED} себе переводить нельзя!", parse_mode="HTML")
        
    sender_xp = await get_xp(sender)
    if sender_xp < amount:
        return await message.answer(f"{E_CAT_SURPRISED} у тебя недостаточно xp! твой баланс: {sender_xp}", parse_mode="HTML")
        
    await update_xp(sender, -amount)
    await update_xp(target, amount)
    
    await message.answer(f"{E_MAGIC} <b>перевод успешен!</b>\n{sender} перевел {amount} xp игроку {target} {E_HEART}", parse_mode="HTML")

# ========== ПЛЕВОК ==========
@dp.message(lambda msg: msg.text and msg.text.lower() == "энди плюнуть")
async def spit_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    if not message.reply_to_message:
        return await message.answer(f"{E_CAT_SURPRISED} в кого плюнуть? ответь на сообщение игрока и напиши 'энди плюнуть' {E_HEART}", parse_mode="HTML")
    target = message.reply_to_message.from_user.first_name or message.reply_to_message.from_user.username or "игрок"
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer(f"{E_CAT_SURPRISED} ты хочешь плюнуть в себя? странно... {E_HEART}", parse_mode="HTML")
    
    success, msg, new_xp = await add_spit(username, target)
    if success:
        await message.answer(f"{msg}\n\n{E_CROWN} у тебя осталось {new_xp} xp {E_MAGIC}", parse_mode="HTML")
        ai_response = await get_enderia_response(f"{username} плюнул в {target}", username, is_reply=True, game_result=f"плевок в {target}")
        if ai_response: await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")
    else:
        await message.answer(f"{E_CAT_SURPRISED} {msg}", parse_mode="HTML")

# ========== ИГРЫ ==========
@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди кубик"))
async def dice_game(message: Message):
    user_id = message.from_user.id
    if user_id in active_players:
        return await message.reply(f"{E_CAT_SURPRISED} подожди, пока закончится прошлая игра!", parse_mode="HTML")
    
    text = message.text.lower()
    match = re.search(r"энди кубик\s+(\d+)", text)
    if not match:
        return await message.reply(f"{E_CAT_DANCE} напиши ставку например: энди кубик 100 {E_JOYSTICK}", parse_mode="HTML")
    
    bet_amount = int(match.group(1))
    if bet_amount <= 0 or bet_amount > 500000:
        return await message.reply(f"{E_CAT_SURPRISED} ставка должна быть от 1 до 500 000 xp!", parse_mode="HTML")
        
    active_players.add(user_id)
    try:
        username = message.from_user.username or message.from_user.first_name
        result_text, _ = await game_dice_bet(username, bet_amount, bot, message.chat.id)
        await message.answer(result_text, parse_mode="HTML")
    finally:
        active_players.discard(user_id)

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди футбол"))
async def football_game(message: Message):
    user_id = message.from_user.id
    if user_id in active_players:
        return await message.reply(f"{E_CAT_SURPRISED} подожди, пока закончится прошлая игра!", parse_mode="HTML")
    
    text = message.text.lower()
    match = re.search(r"энди футбол\s+(\d+)", text)
    if not match:
        return await message.reply(f"{E_CAT_DANCE} напиши ставку например: энди футбол 100 ⚽", parse_mode="HTML")
    
    bet_amount = int(match.group(1))
    if bet_amount <= 0 or bet_amount > 500000:
        return await message.reply(f"{E_CAT_SURPRISED} ставка должна быть от 1 до 500 000 xp!", parse_mode="HTML")
        
    active_players.add(user_id)
    try:
        username = message.from_user.username or message.from_user.first_name
        result_text, _ = await game_football_bet(username, bet_amount, bot, message.chat.id)
        await message.answer(result_text, parse_mode="HTML")
    finally:
        active_players.discard(user_id)

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди слоты"))
async def slots_game(message: Message):
    user_id = message.from_user.id
    if user_id in active_players:
        return await message.reply(f"{E_CAT_SURPRISED} подожди, пока закончится прошлая игра!", parse_mode="HTML")
    
    match = re.search(r"энди слоты\s+(\d+)", message.text.lower())
    if not match:
        return await message.reply(f"{E_CAT_DANCE} напиши ставку например: энди слоты 100 🎰", parse_mode="HTML")
    
    bet_amount = int(match.group(1))
    if bet_amount <= 0 or bet_amount > 500000:
        return await message.reply(f"{E_CAT_SURPRISED} ставка должна быть от 1 до 500 000 xp!", parse_mode="HTML")
        
    active_players.add(user_id)
    try:
        username = message.from_user.username or message.from_user.first_name
        result_text, _ = await game_slots_bet(username, bet_amount, bot, message.chat.id)
        await message.answer(result_text, parse_mode="HTML")
    finally:
        active_players.discard(user_id)

# ========== ФАРМА ==========
@dp.message(lambda msg: msg.text and msg.text.lower() == "энди фарма")
async def farm_collect_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    result_text, game_result = await collect_farm(username)
    await message.answer(result_text, parse_mode="HTML")
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response: await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди фарма инфо")
async def farm_info_cmd(message: Message):
    await message.answer(await farm_info(message.from_user.username or message.from_user.first_name), parse_mode="HTML")

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди улучши фарму")
async def farm_upgrade_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    result_text, game_result = await upgrade_farm_cmd(username)
    await message.answer(result_text, parse_mode="HTML")
    if game_result:
        ai_response = await get_enderia_response(f"{username} {game_result}", username, is_reply=True, game_result=game_result)
        if ai_response: await message.answer(f"{E_CAT_DANCE} {ai_response}", parse_mode="HTML")

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
@dp.message()
async def handle_message(message: Message):
    global CHAT_ID
    if CHAT_ID is None:
        CHAT_ID = message.chat.id
        asyncio.create_task(send_spontaneous_message(bot, CHAT_ID))
    
    if not message.text or message.text.startswith("/"):
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    is_reply_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    
    if should_respond(user_message) or is_reply_to_bot:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        response = await get_enderia_response(user_message, username, is_reply=is_reply_to_bot)
        
        if response == "BUNKER_CREATE_GAME":
            await bunker_command(message)
        elif response:
            await message.reply(response, parse_mode="HTML")
    else:
        await save_chat_message(username, user_message, is_bot=False)

# ========== ИГРА БУНКЕР ==========

@dp.message(lambda msg: msg.text and msg.text.lower() == "энди бункер")
async def bunker_command(message: Message):
    """Создать игру в бункер"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    if chat_id in bunker_lobbies:
        return await message.answer(
            f"{E_CAT_SURPRISED} лобби уже существует! нажми 'играть' чтобы присоединиться",
            parse_mode="HTML"
        )
    
    if chat_id in active_bunker_games:
        return await message.answer(
            f"{E_CAT_SURPRISED} игра уже идёт! дождись окончания",
            parse_mode="HTML"
        )
    
    game = BunkerGame(chat_id, user_id, bot)
    game.players[user_id] = BunkerPlayer(user_id=user_id, username=username)
    bunker_lobbies[chat_id] = game
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ПРИСОЕДИНИТЬСЯ", callback_data="bunker_join")],
        [InlineKeyboardButton(text="🚀 НАЧАТЬ (5-10 игроков)", callback_data="bunker_start")],
        [InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data="bunker_cancel")]
    ])
    
    await message.answer(
        f"{E_CROWN} 🧟 <b>БУНКЕР 2.0</b> 🧟 {E_CROWN}\n\n"
        f"{E_MAGIC} <b>игроков:</b> {len(game.players)}/10\n"
        f"{E_HOUSE} <b>создатель:</b> {username}\n\n"
        f"<i>для старта нужно от 5 до 10 игроков!\n"
        f"каждый получит роль в ЛС и будет раскрывать информацию о себе</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "bunker_join")
async def bunker_join_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    
    if chat_id not in bunker_lobbies:
        await callback.answer("❌ лобби не найдено", show_alert=True)
        return
    
    game = bunker_lobbies[chat_id]
    
    if game.state != GameState.WAITING:
        await callback.answer("❌ игра уже началась", show_alert=True)
        return
    
    if user_id in game.players:
        await callback.answer("❌ ты уже в игре", show_alert=True)
        return
    
    if len(game.players) >= 10:
        await callback.answer("❌ лобби заполнено (максимум 10)", show_alert=True)
        return
    
    game.players[user_id] = BunkerPlayer(user_id=user_id, username=username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ПРИСОЕДИНИТЬСЯ", callback_data="bunker_join")],
        [InlineKeyboardButton(text="🚀 НАЧАТЬ (5-10 игроков)", callback_data="bunker_start")],
        [InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data="bunker_cancel")]
    ])
    
    players_list = "\n".join([f"• {p.username}" for p in game.players.values()])
    
    try:
        await callback.message.edit_text(
            f"{E_CROWN} 🧟 <b>БУНКЕР 2.0</b> 🧟 {E_CROWN}\n\n"
            f"{E_MAGIC} <b>игроков:</b> {len(game.players)}/10\n"
            f"{E_HOUSE} <b>участники:</b>\n{players_list}\n\n"
            f"<i>для старта нужно от 5 до 10 игроков!</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка обновления сообщения: {e}")
    
    await callback.answer(f"✅ {username}, ты присоединился к игре!")

@dp.callback_query(lambda c: c.data == "bunker_start")
async def bunker_start_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in bunker_lobbies:
        await callback.answer("❌ лобби не найдено", show_alert=True)
        return
    
    game = bunker_lobbies[chat_id]
    
    if user_id != game.host_id:
        await callback.answer("❌ только создатель может начать игру", show_alert=True)
        return
    
    if not game.can_start():
        await callback.answer(f"❌ нужно от 5 до 10 игроков! сейчас {len(game.players)}", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"{E_MAGIC} <b>генерация персонажей...</b>\n\n"
        f"<i>каждому игроку отправлена его роль в ЛС!\n"
        f"проверьте личные сообщения @lostearth_bot</i>",
        parse_mode="HTML"
    )
    
    await game.generate_all_characters()
    await asyncio.sleep(3)
    
    active_bunker_games[chat_id] = game
    del bunker_lobbies[chat_id]
    
    await game.start_reveal_phase()
    await callback.answer("✅ Игра началась! Проверьте ЛС бота!")

@dp.callback_query(lambda c: c.data == "bunker_cancel")
async def bunker_cancel_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in bunker_lobbies:
        await callback.answer("❌ лобби не найдено", show_alert=True)
        return
    
    game = bunker_lobbies[chat_id]
    
    if user_id != game.host_id:
        await callback.answer("❌ только создатель может отменить игру", show_alert=True)
        return
    
    del bunker_lobbies[chat_id]
    
    try:
        await callback.message.edit_text(f"{E_CAT_SURPRISED} игра отменена!", parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отмены: {e}")
    
    await callback.answer("✅ игра отменена")

# ========== КОЛБЭКИ ДЛЯ РАСКРЫТИЯ ==========

@dp.callback_query(lambda c: c.data and c.data.startswith("reveal_"))
async def bunker_reveal_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    key = callback.data.split("_")[1]
    
    if key == "locked":
        await callback.answer("❌ ты уже раскрыл характеристику в этом раунде!", show_alert=True)
        return
    
    game = None
    for g in active_bunker_games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await callback.answer("❌ игра не найдена", show_alert=True)
        return
    
    if game.state != GameState.REVEALING:
        await callback.answer("❌ сейчас не время для раскрытия", show_alert=True)
        return
    
    player = game.players[user_id]
    
    if not player.is_alive:
        await callback.answer("❌ ты выбыл", show_alert=True)
        return
    
    if player.has_revealed_this_round:
        await callback.answer("❌ ты уже раскрыл характеристику в этом раунде!", show_alert=True)
        return
    
    if key in player.revealed:
        player.revealed.remove(key)
    else:
        if player.revealed:
            old_key = player.revealed[0]
            player.revealed.remove(old_key)
        player.revealed.append(key)
    
    keyboard = game.get_reveal_keyboard(player)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка обновления: {e}")
    
    await callback.answer("✅ выбор сохранён!")

@dp.callback_query(lambda c: c.data == "reveal_done")
async def bunker_reveal_done_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    game = None
    for g in active_bunker_games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await callback.answer("❌ игра не найдена", show_alert=True)
        return
    
    if game.state != GameState.REVEALING:
        await callback.answer("❌ сейчас не время", show_alert=True)
        return
    
    player = game.players[user_id]
    
    if not player.is_alive:
        await callback.answer("❌ ты выбыл", show_alert=True)
        return
    
    if not player.revealed:
        await callback.answer("❌ выбери хотя бы одну характеристику!", show_alert=True)
        return
    
    player.has_revealed_this_round = True
    
    await callback.message.edit_text(
        f"{E_CAT_OK} <b>ты готов!</b>\n\n"
        f"<i>жду остальных игроков...</i>",
        parse_mode="HTML"
    )
    
    all_ready = True
    for p in game.get_alive_players():
        if not p.has_revealed_this_round:
            all_ready = False
            break
    
    if all_ready:
        await game.start_voting_phase()
    
    await callback.answer("✅ готово!")

# ========== КОЛБЭКИ ДЛЯ ГОЛОСОВАНИЯ ==========

@dp.callback_query(lambda c: c.data and c.data.startswith("vote_"))
async def bunker_vote_callback(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    voter_id = callback.from_user.id
    
    game = None
    for g in active_bunker_games.values():
        if voter_id in g.players:
            game = g
            break
    
    if not game:
        await callback.answer("❌ игра не найдена", show_alert=True)
        return
    
    if game.state != GameState.VOTING:
        await callback.answer("❌ сейчас не время для голосования", show_alert=True)
        return
    
    voter = game.players[voter_id]
    target = game.players[target_id]
    
    if not voter or not voter.is_alive:
        await callback.answer("❌ ты не можешь голосовать", show_alert=True)
        return
    
    if not target or not target.is_alive:
        await callback.answer("❌ этот игрок уже выбыл", show_alert=True)
        return
    
    if voter.has_voted:
        await callback.answer("❌ ты уже проголосовал", show_alert=True)
        return
    
    target.vote_count += 1
    voter.has_voted = True
    
    await callback.message.edit_text(
        f"✅ ты проголосовал против {target.username}!\n\n<i>жду остальных...</i>",
        parse_mode="HTML"
    )
    
    all_voted = True
    for p in game.get_alive_players():
        if not p.has_voted:
            all_voted = False
            break
    
    if all_voted:
        await game.finish_voting()
    
    await callback.answer(f"✅ голос за {target.username} принят!", show_alert=True)

@dp.callback_query(lambda c: c.data == "vote_skip")
async def bunker_vote_skip_callback(callback: CallbackQuery):
    voter_id = callback.from_user.id
    
    game = None
    for g in active_bunker_games.values():
        if voter_id in g.players:
            game = g
            break
    
    if not game:
        await callback.answer("❌ игра не найдена", show_alert=True)
        return
    
    if game.state != GameState.VOTING:
        await callback.answer("❌ сейчас не время", show_alert=True)
        return
    
    voter = game.players[voter_id]
    
    if not voter or not voter.is_alive:
        await callback.answer("❌ ты не можешь голосовать", show_alert=True)
        return
    
    if voter.has_voted:
        await callback.answer("❌ ты уже проголосовал", show_alert=True)
        return
    
    voter.has_voted = True
    
    await callback.message.edit_text(
        f"⏭️ ты пропустил голосование\n\n<i>жду остальных...</i>",
        parse_mode="HTML"
    )
    
    all_voted = True
    for p in game.get_alive_players():
        if not p.has_voted:
            all_voted = False
            break
    
    if all_voted:
        await game.finish_voting()
    
    await callback.answer("✅ пропущено")

# ========== ОБЩИЙ КОЛБЭК ДЛЯ МЕНЮ ==========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    data = callback.data
    
    if data == "menu_main":
        await callback.message.edit_text(f"{E_HEART} <b>главное меню</b>\n\n{E_CAT_DANCE} используй команды или спроси у энди!", parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        await callback.message.edit_text(f"{E_CROWN} <b>lostearth</b> {E_CROWN}\n\n{E_HOUSE} <b>java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>приятной игры</i>", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    elif data == "menu_premium":
        await callback.message.edit_text(f"{E_CROWN} <b>премиум доступ</b> {E_CROWN}\n\n{E_MAGIC} <b>друид</b> - 50₽\n{E_NOTE} <b>оракул</b> - 100₽\n{E_CROWN} <b>монарх</b> - 200₽\n{E_RABBIT} <b>херувим</b> - 300₽\n{E_HOUSE} <b>архонт</b> - 400₽\n{E_CAT_DANCE} <b>серафим</b> - 600₽\n\n{E_HEART} <b>по вопросам:</b> @pelmewki379", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    elif data == "menu_enderia":
        await callback.message.edit_text(f"{E_HEART} <b>энди - твой помощник</b> {E_HEART}\n\n{E_CAT_DANCE} напиши 'энди' и я отвечу\n\n📝 команды: /games", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    elif data == "menu_farm":
        await callback.message.edit_text(f"{E_HOUSE} напиши 'энди фарма инфо' для информации о фарме", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()
    elif data == "menu_top":
        await callback.message.edit_text(f"{E_CROWN} /leaderboard - топ игроков", parse_mode="HTML", reply_markup=get_back_keyboard())
        await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    await connect_db()
    asyncio.create_task(update_online_loop())
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("бот lostearth запущен")
    print(f"бот: @{bot_info.username}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
