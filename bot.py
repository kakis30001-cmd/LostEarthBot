import asyncio
import logging
import os
import socket
import struct
import json
import random
from threading import Thread

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__, static_folder='static')

@flask_app.route('/')
def index():
    return send_from_directory('static', 'rules.html')

@flask_app.route('/apply')
def apply():
    return send_from_directory('static', 'apply.html')

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ========== КОНФИГУРАЦИЯ ==========
SERVER_JAVA_IP = "150.241.85.40"
SERVER_JAVA_PORT = 25565
SERVER_BEDROCK_IP = "150.241.85.40"
SERVER_BEDROCK_PORT = 19132
SERVER_VERSION = "1.21—1.26+"

# ПРАВИЛЬНАЯ HTTPS ССЫЛКА
BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

# ========== ПРЕМИУМ ЭМОДЗИ ==========
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "cat_dance": "5359444458930718519",
    "cat_kiss": "6325462176660195024",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "door": "5873147866364514353",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "start": "5870921127685001066",
}

def emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# ========== ФУНКЦИИ MINECRAFT ==========
async def get_minecraft_online():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((SERVER_JAVA_IP, SERVER_JAVA_PORT))
        
        handshake = bytearray()
        handshake += b'\x00'
        handshake += b'\x04\x00\x00\x00'
        host_bytes = SERVER_JAVA_IP.encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', SERVER_JAVA_PORT)
        handshake += b'\x01'
        
        value = len(handshake)
        while True:
            if value & ~0x7F == 0:
                sock.send(bytes([value]))
                break
            sock.send(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        
        sock.send(handshake)
        sock.send(b'\x00\x00')
        
        result = 0
        shift = 0
        while True:
            byte = sock.recv(1)[0]
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                length = result
                break
        
        data = b''
        while len(data) < length:
            data += sock.recv(1024)
        sock.close()
        
        data = data[1:]
        json_data = json.loads(data.decode('utf-8'))
        players = json_data.get("players", {})
        return players.get("online", 0)
    except Exception as e:
        logger.error(f"Ошибка онлайна: {e}")
        return 0

# ========== УМНАЯ ЭНДЕРИЯ (ОТВЕЧАЕТ ПО ДЕЛУ) ==========
async def get_enderia_response(user_message, username):
    """Эндерия отвечает умно, а не рандомно"""
    msg_lower = user_message.lower()
    
    # Вопросы про IP
    if "айпи" in msg_lower or "ip" in msg_lower or "подключиться" in msg_lower:
        return f"Приветик, {username}! 💜 IP для Java: <code>150.241.85.40:25565</code>, для Bedrock: <code>150.241.85.40:19132</code>. Версия 1.21—1.26+! Телепортируйся к нам 🐱"
    
    # Вопросы про онлайн
    if "онлайн" in msg_lower or "сколько людей" in msg_lower or "игроков" in msg_lower:
        online = await get_minecraft_online()
        return f"Сейчас на сервере играет <b>{online}</b> игроков, {username}! Можешь проверить командой /online 💜✨"
    
    # Вопросы про донаты
    if "донат" in msg_lower or "премиум" in msg_lower or "купить" in msg_lower:
        return f"Ой, {username}! Донаты принимает @pelmewki379 💎 Цены: Друид 50₽, Оракул 100₽, Монарх 200₽, Херувим 300₽, Архонт 400₽, Серафим 600₽. Всё подробнее в меню \"ПРЕМИУМ\" 🐱"
    
    # Вопросы про правила
    if "правил" in msg_lower or "наруш" in msg_lower or "бан" in msg_lower:
        return f"Правила кратко: {username}, читы = бан, на спавне не гриферить, уважать других. Полные правила в меню \"ПРАВИЛА\" 📜💜"
    
    # Вопросы про мирный режим
    if "мирный" in msg_lower or "заявк" in msg_lower:
        return f"Мирный режим — PvP только по согласию, территории защищены. Доступ по заявкам через кнопку \"ЗАЯВКА\" или напиши @pelmewki379 🐰💜"
    
    # Вопросы про SMP
    if "smp" in msg_lower:
        return f"SMP режим — PvP разрешён везде, можно воровать и рейдить. Но читы и лаг-машины = бан! ⚔️💜"
    
    # Приветствия
    if "привет" in msg_lower or "здрав" in msg_lower:
        responses = [
            f"Приветик, {username}! 💜 Как настроение? На сервер зайдешь? 🐱",
            f"Здравствуй, {username}! 🌌 Рада тебя видеть! Чем могу помочь? ✨",
            f"Ой, {username}! Телепортнулась на твой зов! Рассказывай, что случилось? 💜"
        ]
        return random.choice(responses)
    
    # Как дела
    if "как дел" in msg_lower or "как ты" in msg_lower:
        responses = [
            f"У меня всё отлично, {username}! Телепортируюсь по Краю, собираю жемчуг 💜 А у тебя как? 🐱",
            f"Фиолетово~ {username}! У меня всё хорошо. Скучаю по игрокам, заходи на сервер! ✨"
        ]
        return random.choice(responses)
    
    # Про команды
    if "команд" in msg_lower or "/" in msg_lower:
        return f"Доступные команды, {username}: /start, /online, /enderia. А в донатах есть /heal, /fly, /ptime и другие 💜🐱"
    
    # Ответ по умолчанию
    responses = [
        f"Я — Эндерия, {username}! Могу рассказать про IP, онлайн, донаты или правила. Что именно интересует? 💜",
        f"Телепортнулась на твой зов, {username}! Спрашивай про сервер — я всё знаю! ✨🐱",
        f"Фиолетово~ {username}, я слушаю! Расскажи, что хочешь узнать о LostEarth? 🌌"
    ]
    return random.choice(responses)

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            ),
            InlineKeyboardButton(
                text="ЭНДЕРИЯ", 
                callback_data="menu_enderia",
                icon_custom_emoji_id=EMOJI["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"{emoji(EMOJI['start'], '✨')} <b>Добро пожаловать на LostEarth!</b>\n\n"
        f"{emoji(EMOJI['house'], '🏠')} <b>Мирный режим по заявкам!</b>\n\n"
        f"{emoji(EMOJI['cat_ok'], '🐱')} <b>Я Эндерия, твой проводник! Задавай вопросы, обращайся по имени 💜</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(
        f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n"
        f"💻 Сейчас играет: <b>{online}</b> игроков!\n"
        f"{emoji(EMOJI['rabbit_fly'], '🐰')} Присоединяйся: <code>150.241.85.40:25565</code>",
        parse_mode="HTML"
    )

@dp.message(Command("enderia"))
async def cmd_enderia(message: Message):
    text = f"""
{emoji(EMOJI['cat_dance'], '💜')} <b>Привет! Я Эндерия!</b>

🐱 <b>Кто я:</b>
Я девушка-эндермен, хранительница Края.

💬 <b>Что я умею:</b>
• Отвечать на вопросы о сервере
• Рассказывать про донаты и правила
• Помогать новичкам
• Просто болтать

💜 <b>Как ко мне обратиться:</b>
Напиши: <code>Эндер</code>, <code>Эндерия</code>, <code>Энди</code> или <code>Эндер-тян</code>

🐰 <i>Попробуй написать мне что-нибудь с моим именем!</i>
"""
    await message.answer(text, parse_mode="HTML")

# Эндерия отвечает на сообщения
def should_respond_to_enderia(message_text):
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "эндер тян", "энд-тян", "@enderia", "@энд", "@эндерия", "ендер"]
    return any(keyword in text_lower for keyword in keywords)

@dp.message()
async def handle_message(message: Message):
    user_text = message.text
    username = message.from_user.first_name or "Игрок"
    
    if should_respond_to_enderia(user_text):
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            response = await get_enderia_response(user_text, username)
            await message.reply(response, parse_mode="HTML")

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{emoji(EMOJI['cat_dance'], '✨')} <b>Главное меню</b>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{emoji(EMOJI['cat_glasses'], '🔄')} <i>Получаю информацию...</i>",
        parse_mode="HTML"
    )
    
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>Мирный режим по заявкам!</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    
    text = f"""
{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['house'], '🏠')} <i>Мирный режим по заявкам!</i>

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer(f"{emoji(EMOJI['check'], '✅')} Обновлено!")

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '🐱')}{emoji(EMOJI['anime_dance'], '💃')}{emoji(EMOJI['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

{emoji(EMOJI['crown'], '👑')} <b>Привилегии:</b>
• Эксклюзивные ивенты
• Кастомные эмоции
• Приоритетная поддержка
• Уникальный префикс

━━━━━━━━━━━━━━━━━━━━

🌿 <b>Друид</b> — 25₴ / 50₽
🔮 <b>Оракул</b> — 50₴ / 100₽
👑 <b>Монарх</b> — 100₴ / 200₽
🪽 <b>Херувим</b> — 150₴ / 300₽
🏛️ <b>Архонт</b> — 200₴ / 400₽
😇 <b>Серафим</b> — 300₴ / 600₽

━━━━━━━━━━━━━━━━━━━━

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>По вопросам:</b> @pelmewki379

{emoji(EMOJI['cat_kiss'], '😘')} <i>Спасибо за поддержку!</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = f"""
{emoji(EMOJI['cat_dance'], '💜')} <b>Привет! Я Эндерия!</b>

🐱 <b>Кто я:</b>
Я девушка-эндермен, хранительница Края.

💬 <b>Что я умею:</b>
• Отвечать на вопросы о сервере
• Рассказывать про донаты и правила
• Помогать новичкам
• Просто болтать

💜 <b>Как ко мне обратиться:</b>
Напиши: <code>Эндер</code>, <code>Эндерия</code>, <code>Энди</code> или <code>Эндер-тян</code>

🐰 <i>Попробуй написать мне что-нибудь с моим именем!</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
        ])
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("🚀 Бот LostEarth запущен!")
    logger.info(f"📱 Правила: {RULES_URL}")
    logger.info(f"📝 Заявка: {APPLY_URL}")
    logger.info("💜 Эндерия готова к общению!")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
