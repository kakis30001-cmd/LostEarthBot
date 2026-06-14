import asyncio
import os
import re
from datetime import datetime
from threading import Thread
import random

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

# В начале bot.py
from games import (
    add_spit, 
    farm_info, 
    collect_farm, 
    upgrade_farm_cmd, 
    game_dice_bet, 
    game_football_bet,
    game_slots_bet  # <--- Добавь это имя в список
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = -1003891930776  # Зафиксированный ID твоего чата

ADMIN_IDS = [8493522297]

# Анти-спам для игр (хранит ID игроков, которые сейчас играют)
active_players = set()

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

# ========== MINECRAFT API ==========
async def get_java_status(ip: str, port: int = 25565) -> tuple:
    """Проверяет статус Minecraft сервера через mcstatus"""
    try:
        print(f"🔍 Подключаюсь к {ip}:{port}...")
        
        # Используем прямую инициализацию, а не lookup
        server = JavaServer(ip, port)
        status = await server.async_status()
        
        online = status.players.online
        max_players = status.players.max
        
        print(f"✅ Сервер онлайн: {online}/{max_players}")
        return online, max_players
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return 0, 0

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
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    text = message.text.replace("/say", "").strip()
    if not text:
        return await message.answer("📝 /say <текст>\nпример: /say привет всем", parse_mode="HTML")
    await message.answer(f"{E_CAT_DANCE} {text} {E_HEART}", parse_mode="HTML")

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
    # 1. Проверка на админа
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ у тебя нет прав", parse_mode="HTML")
    
    # 2. Разделяем сообщение на части: ["/givexp", "ИмяИгрока", "Сумма"]
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "📝 <b>Использование:</b> <code>/givexp <имя_игрока> <сумма></code>\n"
            "💡 <i>Пример: /givexp Steve 5000</i> (выдать 5000)\n"
            "💡 <i>Пример: /givexp Steve -1000</i> (забрать 1000)", 
            parse_mode="HTML"
        )
    
    target_username = parts[1]
    
    # 3. Проверяем, что сумма — это число
    try:
        amount = int(parts[2])
    except ValueError:
        return await message.answer("❌ Сумма должна быть целым числом!", parse_mode="HTML")
    
    # 4. Начисляем (или списываем) опыт
    await update_xp(target_username, amount)
    
    # 5. Получаем новый баланс для красивого ответа
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
    username = message.from_user.username or message.from_user.first_name
    await create_player(username)
    
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

# ========== ИГРЫ ==========
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

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("энди слоты"))
async def slots_command(message: Message):
    # Достаем ставку из сообщения
    try:
        parts = message.text.split()
        bet = int(parts[2])
    except (IndexError, ValueError):
        return await message.answer("❌ Напиши: <code>энди слоты <сумма></code>", parse_mode="HTML")
    
    username = message.from_user.username or message.from_user.first_name
    
    # Вызываем нашу новую функцию
    result_text, log_msg = await game_slots_bet(username, bet, bot, message.chat.id)
    await message.answer(result_text, parse_mode="HTML")

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
        xp = await get_xp(username)
        if xp < bet_amount:
            await message.reply(f"{E_CAT_SURPRISED} недостаточно xp! твой баланс: {xp}", parse_mode="HTML")
            return
            
        # Забираем ставку
        await update_xp(username, -bet_amount)
        
        # Генерируем 3 числа от 1 до 9
        n1, n2, n3 = random.randint(1, 9), random.randint(1, 9), random.randint(1, 9)
        sevens = [n1, n2, n3].count(7)
        
        if sevens == 3:
            winnings = bet_amount * 4
            await update_xp(username, winnings)
            await update_stats(username, True)
            text = f"🎰 <b>[ {n1} | {n2} | {n3} ]</b>\n\n{E_MAGIC} джекпот! три семерки! ты выиграл {winnings} xp!"
        elif sevens == 2:
            winnings = bet_amount * 3
            await update_xp(username, winnings)
            await update_stats(username, True)
            text = f"🎰 <b>[ {n1} | {n2} | {n3} ]</b>\n\n{E_CROWN} отличный улов! две семерки! ты выиграл {winnings} xp!"
        else:
            await update_stats(username, False)
            text = f"🎰 <b>[ {n1} | {n2} | {n3} ]</b>\n\n{E_CAT_SURPRISED} эх, ничего не совпало. ты проиграл {bet_amount} xp."
            
        new_xp = await get_xp(username)
        text += f"\n💰 твой баланс: {new_xp} xp"
        await message.answer(text, parse_mode="HTML")
    finally:
        active_players.discard(user_id)

# ========== ФАРМА ========== (и далее всё как было)
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

# ========== ОБРАБОТЧИК ==========
@dp.message()
async def handle_message(message: Message):
    if not message.text or message.text.startswith("/"):
        return
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    is_reply_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    
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
        await callback.message.edit_text(f"{E_HEART} <b>главное меню</b>\n\n{E_CROWN} онлайн: {online}/{max_players}\n\n{E_CAT_DANCE} /games - все команды", parse_mode="HTML", reply_markup=get_main_keyboard())
        await callback.answer()
    elif data == "menu_ip":
        online, max_players = await get_server_online()
        await callback.message.edit_text(f"{E_CROWN} <b>lostearth</b> {E_CROWN}\n\n{E_HOUSE} <b>java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>приятной игры</i>", parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer()
    elif data == "refresh_online":
        online_cache.clear()
        last_update.clear()
        online, max_players = await get_server_online()
        current_time = datetime.now().strftime("%H:%M:%S")
        try:
            await callback.message.edit_text(f"{E_CROWN} <b>lostearth</b> {E_CROWN}\n\n{E_HOUSE} <b>java:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n{E_NOTE} <b>bedrock:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n{E_CROWN} <b>онлайн:</b> {online}/{max_players}\n\n{E_RABBIT} <i>приятной игры</i>\n🕒 <i>обновлено: {current_time}</i>", parse_mode="HTML", reply_markup=get_ip_keyboard())
        except TelegramBadRequest:
            pass
        await callback.answer("онлайн обновлён")
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
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("бот lostearth запущен")
    print(f"бот: @{bot_info.username}")
    print("=" * 50)
    
    # Запускаем один раз цикл сообщений строго в нужную группу
    asyncio.create_task(send_spontaneous_message(bot, GROUP_CHAT_ID))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
