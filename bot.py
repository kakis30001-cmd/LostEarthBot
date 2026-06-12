import asyncio
import os
import socket
import struct
import json
import random
import re
from datetime import datetime
from threading import Thread

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from flask import Flask, send_from_directory

from prompts import get_enderia_emojis, emoji, ENDERIA_EMOJI, get_system_prompt
from database import (
    get_balance_sync, update_balance_sync, update_stats_sync, 
    get_stats_sync, can_claim_daily_bonus, claim_daily_bonus,
    load_players, save_players
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

# ========== FLASK ДЛЯ WEBAPP ==========
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

# ========== КОНФИГ ==========
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

# Кэш онлайна
online_cache = {}
last_update = {}

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def random_cat():
    cats = [ENDERIA_EMOJI["cat_dance"], ENDERIA_EMOJI["cat_ok"], ENDERIA_EMOJI["cat_up"], ENDERIA_EMOJI["cat_laugh"]]
    return emoji(random.choice(cats), "🐱")

def random_rabbit():
    return emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")

def random_heart():
    return emoji(ENDERIA_EMOJI["heart"], "💜")

def random_anime():
    return emoji(ENDERIA_EMOJI["anime_dance"], "💃")

def get_random_emoji():
    return get_enderia_emojis(1)

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
    return online, max_players

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="IP И ОНЛАЙН", callback_data="menu_ip")],
        [InlineKeyboardButton(text="ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL)),
         InlineKeyboardButton(text="ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL))],
        [InlineKeyboardButton(text="ПРЕМИУМ", callback_data="menu_premium"),
         InlineKeyboardButton(text="ЭНДЕРИЯ", callback_data="menu_enderia")]
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

# ========== ИГРЫ ==========
async def roll_dice_animated(chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    online, max_players = await get_server_online()
    
    text = f"""✨ <b>Добро пожаловать на {SERVER['name']}</b>

🏠 <b>{SERVER['mode']}</b>

{random_cat()} <b>Я Эндерия - твой живой помощник!</b>

📊 <b>Текущий онлайн:</b> {online}/{max_players}

💰 <b>Игры с Эндерией:</b>
/bet [сумма] - Ставка на кубик (выигрыш x2)
/balance - Твой баланс
/profile - Твой профиль
/daily - Ежедневный бонус 100💎

✨ <b>Стартовый баланс: 100 алмазов</b>
💎 <b>Минимальная ставка: 10 алмазов</b>

🎁 <b>Как получить бонус?</b>
Добавь в описание профиля: @lostearth_bot

{random_rabbit()} {random_anime()} {get_enderia_emojis(1)}"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    await message.answer(f"📊 <b>Онлайн: {online}/{max_players}</b> {random_cat()}", parse_mode="HTML")

@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance_sync(username)
    await message.answer(f"{get_random_emoji()} {username}, твой баланс: {balance} 💎 алмазов! {get_random_emoji()}", parse_mode="HTML")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    balance = get_balance_sync(username)
    stats = get_stats_sync(username)
    
    text = f"""{random_cat()} 👤 <b>ПРОФИЛЬ ИГРОКА</b> {random_cat()}

👤 Имя: {username}
💎 Баланс: {balance} алмазов
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
📊 Всего игр: {stats['wins'] + stats['losses']}

🎁 <b>Ежедневный бонус: +100 алмазов</b>
📝 Добавь в описание: @lostearth_bot

{get_random_emoji()} Напиши /daily чтобы получить бонус! {get_random_emoji()}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("daily"))
async def daily_cmd(message: Message):
    from datetime import date
    username = message.from_user.username or message.from_user.first_name
    
    # Получаем описание профиля
    try:
        user = await bot.get_chat(message.from_user.id)
        user_bio = user.bio if user.bio else ""
        has_bot_in_bio = "@lostearth_bot" in user_bio.lower()
    except:
        has_bot_in_bio = False
    
    if not has_bot_in_bio:
        text = f"""{random_cat()} ❌ <b>НЕТ БОНУСА!</b> {random_cat()}

Чтобы получать ежедневный бонус 100 алмазов, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

{get_random_emoji()} После добавления напиши /daily снова! {get_random_emoji()}"""
        await message.answer(text, parse_mode="HTML")
        return
    
    if can_claim_daily_bonus(username):
        await claim_daily_bonus(username)
        balance = get_balance_sync(username)
        text = f"{random_anime()} 🎁 ЕЖЕДНЕВНЫЙ БОНУС! {random_anime()}\n\n✨ +100 💎 алмазов!\n💎 Баланс: {balance} алмазов\n\n{random_rabbit()} Заходи завтра снова! {random_rabbit()}"
        await message.answer(text, parse_mode="HTML")
    else:
        text = f"{get_random_emoji()} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {random_heart()}"
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("bet"))
async def bet_cmd(message: Message):
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text
    
    match = re.match(r"^/bet\s+(\d+)$", user_message)
    if not match:
        await message.answer(f"{get_random_emoji()} {username}, используй: /bet [сумма] (например /bet 50) 🎲\n💰 Минимальная ставка: 10 алмазов", parse_mode="HTML")
        return
    
    bet_amount = int(match.group(1))
    balance = get_balance_sync(username)
    
    if bet_amount < 10:
        await message.answer(f"{get_random_emoji()} {username}, минимальная ставка 10 алмазов! 💎", parse_mode="HTML")
        return
    
    if balance < bet_amount:
        await message.answer(f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎", parse_mode="HTML")
        return
    
    await message.answer(f"{get_random_emoji()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(message.chat.id)
    
    await asyncio.sleep(1.5)
    await message.answer(f"{get_random_emoji()} Эндерия бросает кубик... 🎲")
    bot_value = await roll_dice_animated(message.chat.id)
    
    if player_value > bot_value:
        update_balance_sync(username, bet_amount)
        update_stats_sync(username, is_win=True)
        new_balance = get_balance_sync(username)
        await message.answer(
            f"{random_cat()} 🎉 ПОБЕДА! {random_cat()}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"✨ Ты выиграл {bet_amount} алмазов!\n"
            f"💎 Баланс: {new_balance} {get_random_emoji()}",
            parse_mode="HTML"
        )
    elif player_value < bot_value:
        update_balance_sync(username, -bet_amount)
        update_stats_sync(username, is_win=False)
        new_balance = get_balance_sync(username)
        await message.answer(
            f"{random_cat()} 😔 ПРОИГРЫШ... {random_cat()}\n\n"
            f"Твой кубик: {player_value}\n"
            f"Мой кубик: {bot_value}\n\n"
            f"💔 Ты проиграл {bet_amount} алмазов!\n"
            f"💎 Баланс: {new_balance} {get_random_emoji()}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"{random_heart()} 🤝 НИЧЬЯ! {random_heart()}\n\n"
            f"Оба выбросили {player_value}\n\n"
            f"💰 Ставка возвращена!\n"
            f"💎 Баланс: {balance} {get_random_emoji()}",
            parse_mode="HTML"
        )

@dp.message(Command("games"))
async def games_cmd(message: Message):
    text = f"""{random_cat()} 🎮 <b>ДОСТУПНЫЕ ИГРЫ</b> {random_cat()}

💰 <b>/bet [сумма]</b> - Ставка на кубик (выигрыш x2)
💎 <b>/balance</b> - Показать баланс
👤 <b>/profile</b> - Твой профиль
🎁 <b>/daily</b> - Ежедневный бонус 100💎

✨ <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Твой кубик против кубика Эндерии
• Если твой кубик больше - выигрываешь x2

💎 <b>Стартовый баланс: 100 алмазов</b>

🎁 <b>Ежедневный бонус:</b>
Добавь @lostearth_bot в описание профиля!

{get_random_emoji()} Напиши /bet 50 чтобы сыграть! {get_random_emoji()}"""
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    await message.answer(f"{random_heart()} <b>Статистика диалога с Эндерией:</b>\n\nПросто напиши мне что-нибудь, и я запомню наш разговор! 💜", parse_mode="HTML")

@dp.message(Command("clear_memory"))
async def clear_memory_cmd(message: Message):
    await message.answer(f"{random_cat()} ✨ <b>Память очищена!</b>\n\nТеперь мы можем начать новый разговор! {random_heart()}", parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.username or message.from_user.first_name
    user_message = message.text.lower()
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    # Проверяем, обращаются ли к Эндерии
    keywords = ["эндер", "эндерия", "энди", "ендер", "енди"]
    if not any(keyword in user_message for keyword in keywords):
        return
    
    # Простой ответ без ИИ (экономия токенов)
    responses = [
        f"{random_cat()} Слушаю, {username}! Что хотел узнать? Может сыграем в кости? /bet 50 🎲",
        f"{random_heart()} Привет, {username}! Я здесь. Хочешь узнать про сервер или поиграть? 💜",
        f"{random_rabbit()} {username}, я Эндерия! Напиши /games чтобы посмотреть игры, или /daily для бонуса! ✨",
        f"{random_anime()} Обращайся, {username}! Можешь спросить про сервер, донаты или сыграть со мной в кости! 🎲"
    ]
    
    response = random.choice(responses)
    await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""{random_heart()} <b>Главное меню</b>\n\n📊 Онлайн: {online}/{max_players}\n\n{random_cat()} Напиши /games чтобы поиграть в кости!"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except:
        pass
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>\n\n💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 <b>Онлайн:</b> {online}/{max_players}\n\n{random_rabbit()} <i>Приятной игры!</i>"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    except:
        pass
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    online, max_players = await get_server_online()
    text = f"""👑 <b>LOSTEARTH</b>\n\n💻 <b>JAVA:</b> <code>{SERVER['java_ip']}:{SERVER['java_port']}</code>\n📱 <b>BEDROCK:</b> <code>{SERVER['bedrock_ip']}:{SERVER['bedrock_port']}</code>\n📊 <b>Онлайн:</b> {online}/{max_players}\n\n{random_rabbit()} <i>Приятной игры!</i>"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
        await callback.answer("🔄 Онлайн обновлён!", show_alert=False)
    except:
        await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{random_heart()} <b>ПРЕМИУМ ДОСТУП</b>\n\n🌿 <b>Друид</b> - 50₽\n🔮 <b>Оракул</b> - 100₽\n👑 <b>Монарх</b> - 200₽\n🪽 <b>Херувим</b> - 300₽ (полёт!)\n🏛️ <b>Архонт</b> - 400₽\n😇 <b>Серафим</b> - 600₽\n\n📩 <b>По вопросам:</b> @pelmewki379\n\n{random_cat()} <i>Хочешь полёт? Бери Херувима!</i>"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except:
        pass
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""{random_heart()} <b>Эндерия - твой живой помощник</b>\n\n{random_cat()} <b>Кто я?</b>\nЯ девушка-эндермен, хранительница Края.\n\n💬 <b>Как ко мне обратиться:</b>\nНапиши: Эндер, Эндерия, Энди\n\n💰 <b>Игры:</b>\n/bet, /balance, /profile, /daily\n\n🎁 <b>Ежедневный бонус 100💎</b>\nДобавь @lostearth_bot в описание профиля!\n\n{random_rabbit()} <i>Просто позови меня по имени или играй!</i>\n{random_heart()}"""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
    except:
        pass
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    # Запуск Flask
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_info = await bot.get_me()
    print("=" * 50)
    print("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    print(f"🤖 Бот: @{bot_info.username}")
    print("💰 Игры: /bet, /balance, /profile, /daily")
    print("📁 Хранилище: JSON файл (players.json)")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
