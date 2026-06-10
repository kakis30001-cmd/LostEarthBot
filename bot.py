# bot.py
import asyncio
from datetime import datetime
from typing import Dict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, EMOJI, e, SERVER, RULES_TEXT, APPLY_TEXT
from minecraft_api import get_bedrock_status, get_java_status

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Кэш для онлайна
online_cache: Dict[str, Dict] = {}
last_update: Dict[str, float] = {}

async def get_server_online() -> Dict:
    """Получение онлайна сервера с кэшем"""
    now = datetime.now().timestamp()
    
    if "java" in last_update and now - last_update["java"] < 30:
        return online_cache
    
    java_status = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    bedrock_status = await get_bedrock_status(SERVER["bedrock_ip"], SERVER["bedrock_port"])
    
    online_cache["java"] = java_status
    online_cache["bedrock"] = bedrock_status
    last_update["java"] = now
    last_update["bedrock"] = now
    
    return online_cache

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['door'], '🚪')} IP И ОНЛАЙН", 
                callback_data="menu_ip"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['note'], '📜')} ПРАВИЛА", 
                callback_data="menu_rules"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI['rabbit_fly'], '✉️')} ПОДАТЬ ЗАЯВКУ", 
                callback_data="menu_apply"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['premium'], '💎')} ПРЕМИУМ", 
                callback_data="menu_premium"
            )
        ]
    ])

def get_ip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['check'], '🔄')} ОБНОВИТЬ ОНЛАЙН", 
                callback_data="refresh_online"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['back'], '◀️')} НАЗАД", 
                callback_data="menu_main"
            )
        ]
    ])

def get_premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['cat_dance'], '🐱')} КОТИК СТАЙЛ", 
                callback_data="premium_cat"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI['anime_dance'], '🎌')} АНИМЕ СТАЙЛ", 
                callback_data="premium_anime"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['rabbit_fly'], '🐰')} ЗАЙЧИК СТАЙЛ", 
                callback_data="premium_rabbit"
            ),
            InlineKeyboardButton(
                text=f"{e(EMOJI['cat_kiss'], '💝')} ПРЕМИУМ ВСЁ", 
                callback_data="premium_all"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{e(EMOJI['back'], '◀️')} НАЗАД", 
                callback_data="menu_main"
            )
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        f"{e(EMOJI['start'], '🎮')} <b>Добро пожаловать на {SERVER['name']}</b> {e(EMOJI['start'], '🎮')}\n\n"
        f"{e(EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{e(EMOJI['cat_ok'], '🐱')} <i>Выбери действие в меню ниже:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI['start'], '🎮')} <b>Главное меню {SERVER['name']}</b> {e(EMOJI['start'], '🎮')}\n\n"
        f"{e(EMOJI['house'], '🏠')} <b>{SERVER['mode']}</b>\n\n"
        f"{e(EMOJI['cat_ok'], '🐱')} <i>Выбери действие:</i>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI['cat_glasses'], '🔄')} <i>Получаю информацию о сервере...</i>",
        parse_mode="HTML"
    )
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    java_online = java.get("online", 0)
    java_max = java.get("max", 0)
    bedrock_online = bedrock.get("online", 0)
    bedrock_max = bedrock.get("max", 0)
    
    status_emoji = e(EMOJI["cat_up"], "🟢") if java_online > 0 or bedrock_online > 0 else e(EMOJI["cat_surprised"], "🔴")
    status_text = "РАБОТАЕТ" if java_online > 0 or bedrock_online > 0 else "ОФФЛАЙН"
    
    text = f"""
{status_emoji} <b>{SERVER['name']}</b> {status_emoji}
{e(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{e(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

{e(EMOJI['joystick'], '📱')} <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{e(EMOJI['rabbit_fly'], '✨')} <i>Наслаждайся игрой на LostEarth!</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_ip_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    # Очищаем кэш
    online_cache.clear()
    last_update.clear()
    
    await callback.message.edit_text(
        f"{e(EMOJI['cat_dance'], '🔄')} <i>Обновляю онлайн...</i>",
        parse_mode="HTML"
    )
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    java_online = java.get("online", 0)
    java_max = java.get("max", 0)
    bedrock_online = bedrock.get("online", 0)
    bedrock_max = bedrock.get("max", 0)
    
    status_emoji = e(EMOJI["cat_up"], "🟢") if java_online > 0 or bedrock_online > 0 else e(EMOJI["cat_surprised"], "🔴")
    status_text = "РАБОТАЕТ" if java_online > 0 or bedrock_online > 0 else "ОФФЛАЙН"
    
    text = f"""
{status_emoji} <b>{SERVER['name']}</b> {status_emoji}
{e(EMOJI['house'], '🏠')} <i>{SERVER['mode']}</i>

{e(EMOJI['joystick'], '💻')} <b>JAVA EDITION</b>
├ IP: <code>{SERVER['java_ip']}</code>
├ Порт: <code>{SERVER['java_port']}</code>
├ Версия: <code>{SERVER['java_versions']}</code>
└ Онлайн: <b>{java_online}/{java_max}</b>

{e(EMOJI['joystick'], '📱')} <b>BEDROCK EDITION</b>
├ IP: <code>{SERVER['bedrock_ip']}</code>
├ Порт: <code>{SERVER['bedrock_port']}</code>
└ Онлайн: <b>{bedrock_online}/{bedrock_max}</b>

{e(EMOJI['rabbit_fly'], '✨')} <i>Наслаждайся игрой на LostEarth!</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_ip_keyboard()
    )
    await callback.answer(f"{e(EMOJI['cat_up'], '✅')} Онлайн обновлён!")

@dp.callback_query(lambda c: c.data == "menu_rules")
async def menu_rules(callback: CallbackQuery):
    await callback.message.edit_text(
        RULES_TEXT,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI['back'], '◀️')} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_apply")
async def menu_apply(callback: CallbackQuery):
    await callback.message.edit_text(
        APPLY_TEXT,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI['back'], '◀️')} НАЗАД", callback_data="menu_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{e(EMOJI['premium'], '💎')} <b>ПРЕМИУМ ДОСТУП LOSTEARTH</b> {e(EMOJI['premium'], '💎')}\n\n"
        f"{e(EMOJI['cat_dance'], '🐱')} <b>Преимущества:</b>\n"
        f"• {e(EMOJI['crown'], '👑')} Эксклюзивный доступ к ивентам\n"
        f"• {e(EMOJI['anime_dance'], '🎨')} Кастомные эмоции в чате\n"
        f"• {e(EMOJI['rabbit_fly'], '🚀')} Приоритетная поддержка\n"
        f"• {e(EMOJI['cat_kiss'], '💝')} Уникальный префикс в чате\n"
        f"• {e(EMOJI['house'], '🏠')} Приватная территория\n\n"
        f"{e(EMOJI['cat_up'], '👍')} <b>Цена: 299₽ / месяц</b>\n\n"
        f"{e(EMOJI['rabbit_smile'], '🐰')} <i>Выбери стиль оформления премиума:</i>",
        parse_mode="HTML",
        reply_markup=get_premium_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("premium_"))
async def premium_style(callback: CallbackQuery):
    style = callback.data.split("_")[1]
    styles = {
        "cat": f"{e(EMOJI['cat_dance'], '🐱🎵')} КОТИК СТАЙЛ {e(EMOJI['cat_dance'], '🐱🎵')}",
        "anime": f"{e(EMOJI['anime_dance'], '🌸🎌')} АНИМЕ СТАЙЛ {e(EMOJI['anime_dance'], '🌸🎌')}",
        "rabbit": f"{e(EMOJI['rabbit_fly'], '🐰✨')} ЗАЙЧИК СТАЙЛ {e(EMOJI['rabbit_fly'], '🐰✨')}",
        "all": f"{e(EMOJI['cat_dance'], '🐱')}{e(EMOJI['anime_dance'], '🌸')}{e(EMOJI['rabbit_fly'], '🐰')} ПРЕМИУМ {e(EMOJI['rabbit_fly'], '🐰')}{e(EMOJI['anime_dance'], '🌸')}{e(EMOJI['cat_dance'], '🐱')}"
    }
    
    await callback.message.edit_text(
        f"{styles[style]}\n\n"
        f"{e(EMOJI['cat_kiss'], '💎')} <b>Оплата премиум доступа:</b>\n\n"
        f"{e(EMOJI['check'], '✅')} Карта РФ\n"
        f"{e(EMOJI['check'], '✅')} СБП\n"
        f"{e(EMOJI['check'], '✅')} Криптовалюта\n\n"
        f"{e(EMOJI['cat_ok'], '📝')} <i>Для покупки напиши:</i> @nikita1055\n\n"
        f"{e(EMOJI['rabbit_smile'], '🐰')} <b>Твой стиль:</b> {styles[style]}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{e(EMOJI['back'], '◀️')} НАЗАД", callback_data="menu_premium")]
        ])
    )
    await callback.answer()

@dp.message(Command("online"))
async def cmd_online(message: Message):
    await message.answer(f"{e(EMOJI['cat_dance'], '🔄')} <i>Получаю онлайн...</i>", parse_mode="HTML")
    
    online = await get_server_online()
    java = online.get("java", {"online": 0, "max": 0})
    bedrock = online.get("bedrock", {"online": 0, "max": 0})
    
    await message.answer(
        f"{e(EMOJI['joystick'], '📊')} <b>Онлайн {SERVER['name']}</b>\n\n"
        f"💻 Java: <b>{java.get('online', 0)}/{java.get('max', 0)}</b>\n"
        f"📱 Bedrock: <b>{bedrock.get('online', 0)}/{bedrock.get('max', 0)}</b>",
        parse_mode="HTML"
    )

async def main():
    print(f"{e(EMOJI['cat_dance'], '🐱')} Бот LostEarth запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
