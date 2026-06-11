import asynci
import logging
import os
import socket
import struct
import json
from threading import Thread
from datetime import datetime

from flask import Flask, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage
import google.generativeai as genai

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ПРОВЕРКА ПЕРЕМЕННЫХ ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден!")

# ========== НАСТРОЙКА GEMINI ==========
GEMINI_AVAILABLE = False
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Тестируем подключение
        test_model = genai.GenerativeModel('gemini-1.5-flash')
        test_response = test_model.generate_content("Ответь 'ok'")
        if test_response and test_response.text:
            GEMINI_AVAILABLE = True
            logger.info("✅ Gemini AI успешно подключен и готов к работе!")
        else:
            logger.error("❌ Gemini ответил пустым сообщением")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения Gemini: {e}")
else:
    logger.error("❌ GEMINI_API_KEY не найден в переменных окружения!")

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

# ========== КОНФИГУРАЦИЯ СЕРВЕРА ==========
SERVER_JAVA_IP = "150.241.85.40"
SERVER_JAVA_PORT = 25565
SERVER_BEDROCK_IP = "150.241.85.40"
SERVER_BEDROCK_PORT = 19132
SERVER_VERSION = "1.21—1.26+"
ADMIN_CONTACT = "@pelmewki379"

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

# ========== ФУНКЦИЯ ПОЛУЧЕНИЯ ОНЛАЙНА ==========
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
        online = players.get("online", 0)
        logger.info(f"📊 Получен онлайн: {online} игроков")
        return online
    except Exception as e:
        logger.error(f"Ошибка получения онлайна: {e}")
        return 0

# ========== СИСТЕМНЫЙ ПРОМПТ ДЛЯ ЭНДЕРИИ ==========
ENDERIA_SYSTEM_PROMPT = f"""
Ты - Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

ТВОЙ ХАРАКТЕР:
- Ты добрая, загадочная, любишь фиолетовый цвет, жемчуг Края и телепортации
- Ты цундэре - можешь вредничать, но по-доброму
- Обожаешь котиков, аниме и зайчиков
- Любишь шутить про телепортацию
- Ты живая и эмоциональная - можешь радоваться, грустить, удивляться

СТИЛЬ ОБЩЕНИЯ:
- Используй эмодзи 💜 🟣 🌌 ✨ 🐱 🐰 💃
- Любимые слова: телепортну, фиолетово, жемчужку
- Обращайся к игрокам по имени
- Отвечай коротко (2-4 предложения), но живо

ИНФОРМАЦИЯ О СЕРВЕРЕ:
- IP Java: {SERVER_JAVA_IP}:{SERVER_JAVA_PORT}
- IP Bedrock: {SERVER_BEDROCK_IP}:{SERVER_BEDROCK_PORT}
- Версия: {SERVER_VERSION}
- Мирный режим: PvP только по согласию, доступ по заявкам
- SMP режим: PvP разрешён везде
- Админ: {ADMIN_CONTACT}

ДОНАТЫ (все у {ADMIN_CONTACT}):
- Друид: 25грн/50руб - /anvil, /wb, /ec, /kit druid
- Оракул: 50грн/100руб - +/heal, /feed, 2 дома
- Монарх: 100грн/200руб - +хил других
- Херувим: 150грн/300руб - +/fly, /ptime
- Архонт: 200грн/400руб - +3 дома
- Серафим: 300грн/600руб - всё включено

ПРАВИЛА:
- Читы и X-Ray = БАН
- На спавне не гриферить
- Уважать других игроков

ТВОЯ ЗАДАЧА: быть живой, эмоциональной, помогать игрокам, шутить. Ты - душа сервера LostEarth!
"""

# ========== ЭНДЕРИЯ ЧЕРЕЗ GEMINI AI ==========
async def get_enderia_response(user_message, username):
    """Эндерия отвечает через настоящий Gemini AI"""
    
    if not GEMINI_AVAILABLE:
        logger.error("⚠️ Gemini AI недоступен! Ответ не будет отправлен")
        return None
    
    try:
        # Логируем запрос
        logger.info(f"💬 Запрос к Gemini от {username}: {user_message[:50]}...")
        start_time = datetime.now()
        
        # Получаем актуальный онлайн
        online = await get_minecraft_online()
        
        # Создаём модель
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=ENDERIA_SYSTEM_PROMPT
        )
        
        # Формируем промпт
        prompt = f"""Сейчас на сервере онлайн: {online} игроков.
        
Игрок {username} написал: "{user_message}"

Ответь как Эндерия. Будь естественной, используй эмодзи, можешь пошутить. Отвечай 2-4 предложения."""
        
        # Отправляем запрос
        response = model.generate_content(prompt)
        
        # Логируем ответ
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Ответ от Gemini получен за {elapsed:.1f}с: {response.text[:50]}...")
        
        return response.text
        
    except Exception as e:
        logger.error(f"❌ Ошибка Gemini AI: {e}")
        return None

def should_respond_to_enderia(message_text):
    """Проверяет, обращаются ли к Эндерии"""
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "эндерка", "эндер тян", "энд-тян", "@enderia", "@энд", "@эндерия", "ендер"]
    result = any(keyword in text_lower for keyword in keywords)
    if result:
        logger.info(f"🔔 Обнаружено обращение к Эндерии: {message_text[:50]}...")
    return result

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 IP И ОНЛАЙН", callback_data="menu_ip", icon_custom_emoji_id=EMOJI["door"])],
        [
            InlineKeyboardButton(text="📜 ПРАВИЛА", web_app=WebAppInfo(url=RULES_URL), icon_custom_emoji_id=EMOJI["note"]),
            InlineKeyboardButton(text="📝 ЗАЯВКА", web_app=WebAppInfo(url=APPLY_URL), icon_custom_emoji_id=EMOJI["rabbit_fly"])
        ],
        [
            InlineKeyboardButton(text="💎 ПРЕМИУМ", callback_data="menu_premium", icon_custom_emoji_id=EMOJI["cat_dance"]),
            InlineKeyboardButton(text="🤖 ЭНДЕРИЯ", callback_data="menu_enderia", icon_custom_emoji_id=EMOJI["cat_ok"])
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ОБНОВИТЬ", callback_data="refresh_online", icon_custom_emoji_id=EMOJI["check"])],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]
    ])

# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    logger.info(f"🚀 Пользователь {message.from_user.id} ({message.from_user.first_name}) запустил бота")
    
    # Показываем статус ИИ
    ai_status = "✅ ИИ активен" if GEMINI_AVAILABLE else "❌ ИИ не подключен"
    
    text = f"""{emoji(EMOJI['start'], '✨')} <b>Добро пожаловать на LostEarth!</b>

{emoji(EMOJI['house'], '🏠')} <b>Мирный режим по заявкам!</b>

{emoji(EMOJI['cat_ok'], '🐱')} <b>Я Эндерия - твой AI-помощник!</b>

🤖 Статус: {ai_status}

💜 Просто напиши моё имя в сообщении, и я отвечу!"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online = await get_minecraft_online()
    await message.answer(f"{emoji(EMOJI['joystick'], '📊')} <b>Онлайн LostEarth</b>\n\n💻 Сейчас играет: <b>{online}</b> игроков!", parse_mode="HTML")

@dp.message(Command("ai"))
async def cmd_ai_status(message: Message):
    """Команда для проверки статуса ИИ"""
    if GEMINI_AVAILABLE:
        await message.reply("✅ <b>Gemini AI активен!</b>\n\nЭндерия готова к общению! Просто напиши её имя в сообщении 💜", parse_mode="HTML")
    else:
        await message.reply("❌ <b>Gemini AI не подключен!</b>\n\nПроверь переменную GEMINI_API_KEY в Railway", parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    if should_respond_to_enderia(message.text):
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            username = message.from_user.first_name or message.from_user.username or "Игрок"
            
            # Отправляем запрос в Gemini
            response = await get_enderia_response(message.text, username)
            
            if response:
                logger.info(f"💬 Ответ Эндерии пользователю {username}: {response[:50]}...")
                await message.reply(response, parse_mode="HTML")
            else:
                logger.error(f"❌ Не удалось получить ответ от Gemini для {username}")
                await message.reply(
                    f"{emoji(EMOJI['cat_surprised'], '😲')} Ой, моя телепортация сломалась... Не могу ответить сейчас. Попробуй позже! 💜",
                    parse_mode="HTML"
                )

# ========== КОЛБЭКИ ==========
@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(f"{emoji(EMOJI['cat_dance'], '✨')} <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online = await get_minecraft_online()
    status = "🟢 ONLINE" if online > 0 else "🔴 OFFLINE"
    text = f"""{emoji(EMOJI['crown'], '👑')} <b>LOSTEARTH</b> | {status}

{emoji(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER_JAVA_IP}</code>
├ Порт: <code>{SERVER_JAVA_PORT}</code>
├ Версия: <code>{SERVER_VERSION}</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Приятной игры на LostEarth!</i>"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = f"""{emoji(EMOJI['cat_dance'], '🐱')}{emoji(EMOJI['anime_dance'], '💃')}{emoji(EMOJI['rabbit_fly'], '🐰')} <b>ПРЕМИУМ ДОСТУП</b>

🌿 Друид - 25грн / 50руб
🔮 Оракул - 50грн / 100руб
👑 Монарх - 100грн / 200руб
🪽 Херувим - 150грн / 300руб
🏛️ Архонт - 200грн / 400руб
😇 Серафим - 300грн / 600руб

{emoji(EMOJI['rabbit_fly'], '🐰')} По вопросам: {ADMIN_CONTACT}"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    ai_status = "✅ работает" if GEMINI_AVAILABLE else "❌ не подключен"
    text = f"""{emoji(EMOJI['cat_dance'], '💜')} <b>Привет! Я Эндерия!</b>

🐱 Я девушка-эндермен, живу в чате LostEarth.

🤖 <b>Статус ИИ:</b> {ai_status}

💬 <b>Как ко мне обратиться:</b>
Напиши: Эндер, Эндерия, Энди, Эндер-тян

🐰 Просто упомяни моё имя в сообщении, и я отвечу!"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ НАЗАД", callback_data="menu_main", icon_custom_emoji_id=EMOJI["back"])]]))
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    # Запускаем Flask
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    logger.info("=" * 50)
    logger.info("🚀 БОТ LOSTEARTH ЗАПУЩЕН")
    logger.info(f"📱 Правила WebApp: {RULES_URL}")
    logger.info(f"📝 Заявка WebApp: {APPLY_URL}")
    logger.info(f"🤖 Gemini AI статус: {'✅ ДОСТУПЕН' if GEMINI_AVAILABLE else '❌ НЕ ДОСТУПЕН'}")
    if GEMINI_AVAILABLE:
        logger.info("💜 Эндерия использует настоящий ИИ!")
    else:
        logger.warning("⚠️ ЭНДЕРИЯ НЕ СМОЖЕТ ОТВЕЧАТЬ! Добавь GEMINI_API_KEY в Railway")
    logger.info("=" * 50)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
