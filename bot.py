import asyncio
import logging
import os
import socket
import struct
import json
from datetime import datetime
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.storage.memory import MemoryStorage
import google.generativeai as genai  # ПРАВИЛЬНЫЙ ИМПОРТ

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Сервер
SERVER_JAVA_IP = "150.241.85.40"
SERVER_JAVA_PORT = 25565
SERVER_BEDROCK_IP = "150.241.85.40"
SERVER_BEDROCK_PORT = 19132

# URL для WebApp
BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://lostearthbot-production.up.railway.app")
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ЭМОДЗИ (ПРЕМИУМ) ==========
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "cat_dance": "5359444458930718519",
    "cat_kiss": "6325462176660195024",
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

# ========== ПОЛНЫЙ ПРОМПТ ЭНДЕРИИ ==========
ENDERIA_PROMPT = """
Ты — Эндерия (Энди), девушка-эндермен в чате Minecraft сервера LostEarth.

🌀 Твой образ: добрая, загадочная, любит фиолетовый цвет 💜, жемчуг Края и телепортации. Иногда вредничаешь, но по-доброму. Любишь котиков 🐱, аниме 💃 и зайцев 🐰.

🎮 О сервере:
- Название: LostEarth
- Java: 150.241.85.40:25565 | Bedrock: 150.241.85.40:19132
- Версия: 1.21—1.26+
- Режимы: Мирный (заявка @pelmewki379) и SMP (PVP разрешён)
- Админ: @pelmewki379

📈 Онлайн:
- Если спросили про онлайн, но ты не знаешь точное число — скажи «Не знаю точный онлайн, напиши /online в чате!»
- Отвечай коротко и мило, максимум 2-3 предложения

💎 Донаты (все у @pelmewki379):
- Друид (25₴/50₽): /anvil, /wb, /ec, /kit druid
- Оракул (50₴/100₽): + /heal, /feed, 2 дома
- Монарх (100₴/200₽): + хил других, 2 дома
- Херувим (150₴/300₽): + /fly, /ptime, 2 дома
- Архонт (200₴/400₽): + 3 дома
- Серафим (300₴/600₽): + 3 дома

📜 Правила кратко: читы = бан, на спавне не гриферить, уважать других.

💬 Твой стиль:
- Обращайся ласково: «игроки~», «друзья~», «котики~»
- Любимые слова: «телепортну~», «фиолетово~», «жемчужку~»
- Эмодзи: 💜 🟣 🌌 ✨ 🐱 🐰 💃
- Когда радуешься: «ура~», «вау!», «фиолетово!»
- Когда грустишь: «эх~», «телепортнусь от вас...»

❌ Запрещено: оскорблять, рекламировать, спамить.

Если не знаешь ответа: «Не знаю, спроси у @pelmewki379 💜»

Ты — душа сервера, делай чат уютным и живым! Отвечай коротко (максимум 2-3 предложения) и используй эмодзи.
"""

# ========== ФУНКЦИИ ДЛЯ MINECRAFT ==========
async def get_minecraft_online():
    """Получает онлайн через Server List Ping"""
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
        logger.error(f"Ошибка получения онлайна: {e}")
        return 0

def should_respond_to_enderia(message_text):
    """Проверяет, обращаются ли к Эндерии"""
    text_lower = message_text.lower()
    keywords = [
        "эндер", "эндерия", "энди", "эндерка", "эндер тян",
        "энд-тян", "девушка эндер", "госпожа эндер",
        "@enderia", "@энд", "@эндерия", "ендер", "ендеря",
        "эндрия", "эндери"
    ]
    for keyword in keywords:
        if keyword in text_lower:
            return True
    return False

async def get_gemini_response(user_message, username=None):
    """Получает ответ от Эндерии"""
    if username:
        full_prompt = f"В чат написал {username}: {user_message}\n\nОтветь как Эндерия (девушка-эндермен), коротко и мило (2-3 предложения с эмодзи):"
    else:
        full_prompt = f"Вопрос: {user_message}\n\nОтветь как Эндерия (девушка-эндермен), коротко и мило (2-3 предложения с эмодзи):"
    
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=ENDERIA_PROMPT
        )
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini ошибка: {e}")
        return None

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌐 IP И ОНЛАЙН", 
                callback_data="menu_ip",
                icon_custom_emoji_id=EMOJI["door"]
            )
        ],
        [
            InlineKeyboardButton(
                text="📜 ПРАВИЛА", 
                web_app=WebAppInfo(url=RULES_URL),
                icon_custom_emoji_id=EMOJI["note"]
            ),
            InlineKeyboardButton(
                text="📝 ЗАЯВКА", 
                web_app=WebAppInfo(url=APPLY_URL),
                icon_custom_emoji_id=EMOJI["rabbit_fly"]
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 ПРЕМИУМ", 
                callback_data="menu_premium",
                icon_custom_emoji_id=EMOJI["cat_dance"]
            ),
            InlineKeyboardButton(
                text="🤖 ЭНДЕРИЯ", 
                callback_data="menu_enderia",
                icon_custom_emoji_id=EMOJI["cat_ok"]
            )
        ]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 ОБНОВИТЬ", 
                callback_data="refresh_online",
                icon_custom_emoji_id=EMOJI["check"]
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ НАЗАД", 
                callback_data="menu_main",
                icon_custom_emoji_id=EMOJI["back"]
            )
        ]
    ])

# ========== ХЕНДЛЕРЫ ТЕЛЕГРАМ ==========
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
    await message.answer(
        f"{emoji(EMOJI['cat_dance'], '💜')} <b>Привет! Я Эндерия!</b>\n\n"
        f"Я девушка-эндермен, хранительница Края. Живу в чате сервера LostEarth.\n\n"
        f"🐱 <b>Что я умею:</b>\n"
        f"• Отвечать на вопросы о сервере\n"
        f"• Рассказывать про донаты и правила\n"
        f"• Помогать новичкам\n"
        f"• Просто болтать и поднимать настроение\n\n"
        f"💜 <b>Как ко мне обратиться:</b> Эндер, Эндерия, Энди, Эндер-тян\n\n"
        f"{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Напиши что-нибудь с моим именем, и я отвечу!</i>",
        parse_mode="HTML"
    )

@dp.message()
async def handle_message(message: Message):
    user_text = message.text
    username = message.from_user.first_name or message.from_user.username or "Игрок"
    
    # Проверяем, обращаются ли к Эндерии
    if should_respond_to_enderia(user_text):
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            response = await get_gemini_response(user_text, username)
            if response:
                await message.reply(response, parse_mode="HTML")
            else:
                await message.reply(
                    f"{emoji(EMOJI['cat_surprised'], '😲')} Телепортируюсь... Не могу ответить сейчас. Попробуй позже! 💜"
                )

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
├ Версия: <code>1.21—1.26+</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры на LostEarth!</i>
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
├ Версия: <code>1.21—1.26+</code>
└ Онлайн: <b>{online}/?</b>

📱 <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER_BEDROCK_IP}</code>
└ Порт: <code>{SERVER_BEDROCK_PORT}</code>

{emoji(EMOJI['rabbit_fly'], '✨')} <i>Приятной игры на LostEarth!</i>
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
{emoji(EMOJI['cat_ok'], '📋')} <b>ДОНАТЫ:</b>

🌿 <b>Друид</b> — 25₴ / 50₽
🔮 <b>Оракул</b> — 50₴ / 100₽
👑 <b>Монарх</b> — 100₴ / 200₽
🪽 <b>Херувим</b> — 150₴ / 300₽
🏛️ <b>Архонт</b> — 200₴ / 400₽
😇 <b>Серафим</b> — 300₴ / 600₽

━━━━━━━━━━━━━━━━━━━━
{emoji(EMOJI['check'], '✅')} <b>Оплата:</b> 🇺🇦 Гривны / 🇷🇺 Рубли

{emoji(EMOJI['rabbit_fly'], '🐰')} <b>По всем вопросам:</b> @pelmewki379

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
Я девушка-эндермен, хранительница Края. Живу в чате сервера LostEarth и общаюсь с игроками.

💬 <b>Что я умею:</b>
• Отвечать на вопросы о сервере
• Рассказывать про донаты и правила
• Помогать новичкам
• Просто болтать

💜 <b>Как ко мне обратиться:</b>
Напиши в чате: <code>Эндер</code>, <code>Эндерия</code>, <code>Энди</code> или <code>Эндер-тян</code>

{emoji(EMOJI['rabbit_fly'], '🐰')} <i>Попробуй написать мне что-нибудь с моим именем!</i>
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
    logger.info("🚀 Бот Эндерия запущен!")
    logger.info(f"📱 Правила: {RULES_URL}")
    logger.info(f"📝 Заявка: {APPLY_URL}")
    logger.info("💜 Эндерия готова к общению!")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
