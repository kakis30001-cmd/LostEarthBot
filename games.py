import asyncio
from datetime import datetime

from database import get_xp, update_xp, update_stats

# ========== ПЛЕВОК ==========
async def add_spit(username: str, target: str) -> tuple[bool, str, int]:
    xp = await get_xp(username)
    if xp < 30:
        return False, f"У тебя всего {xp} XP! Нужно 30 XP для плевка!", 0
    
    await update_xp(username, -30)
    new_xp = await get_xp(username)
    return True, f"💨 {username} плюнул(а) в {target} эндер-жемчугом!", new_xp

# ========== ФАРМА ==========
# Данные о фарме для каждого игрока хранятся в БД в таблице players
# Добавляем колонки: farm_level, last_farm

async def init_farm_tables():
    """Инициализация таблиц для фармы"""
    from database import DATABASE_URL
    import asyncpg
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        # Добавляем колонки для фармы если их нет
        await conn.execute("""
            ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_level INTEGER DEFAULT 1,
            ADD COLUMN IF NOT EXISTS last_farm TIMESTAMP DEFAULT NULL
        """)
        await conn.close()
        print("✅ Таблицы фармы инициализированы")
    except Exception as e:
        print(f"Ошибка инициализации фармы: {e}")

async def get_farm_level(username: str) -> int:
    """Получает уровень фармы игрока"""
    from database import DATABASE_URL
    import asyncpg
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT farm_level FROM players WHERE username = $1", username)
        await conn.close()
        if row:
            return row[0]
        return 1
    except:
        return 1

async def get_last_farm(username: str):
    """Получает время последнего сбора фармы"""
    from database import DATABASE_URL
    import asyncpg
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT last_farm FROM players WHERE username = $1", username)
        await conn.close()
        if row and row[0]:
            return row[0]
        return None
    except:
        return None

async def update_farm_level(username: str, new_level: int):
    """Обновляет уровень фармы"""
    from database import DATABASE_URL
    import asyncpg
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET farm_level = $1 WHERE username = $2", new_level, username)
        await conn.close()
    except Exception as e:
        print(f"Ошибка обновления уровня фармы: {e}")

async def update_last_farm(username: str):
    """Обновляет время последнего сбора фармы"""
    from database import DATABASE_URL
    import asyncpg
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET last_farm = NOW() WHERE username = $1", username)
        await conn.close()
    except Exception as e:
        print(f"Ошибка обновления времени фармы: {e}")

# Доход от фармы в зависимости от уровня
FARM_INCOME = {
    1: 50,
    2: 100,
    3: 200,
    4: 350,
    5: 550,
    6: 800,
    7: 1100,
    8: 1500,
    9: 2000,
    10: 3000,
}

# Стоимость прокачки уровня
UPGRADE_COST = {
    1: 0,
    2: 500,
    3: 1000,
    4: 2000,
    5: 3500,
    6: 5500,
    7: 8000,
    8: 11000,
    9: 15000,
    10: 20000,
}

async def farm_info(username: str, has_bot_in_bio: bool) -> str:
    """Показывает информацию о фарме"""
    if not has_bot_in_bio:
        return f"""❌ ФАРМА НЕ ДОСТУПНА!

Чтобы пользоваться фармой, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 Как это сделать:
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

После добавления бот проверит и фарма заработает! 💜"""
    
    level = await get_farm_level(username)
    income = FARM_INCOME.get(level, 50)
    next_cost = UPGRADE_COST.get(level + 1, "MAX")
    xp = await get_xp(username)
    last_farm = await get_last_farm(username)
    
    text = f"🏭 <b>ТВОЯ ФАРМА</b> 🏭\n\n"
    text += f"📊 Уровень: {level}\n"
    text += f"💰 Доход за сбор: {income} XP\n"
    text += f"⏰ Перезарядка: 3 часа\n"
    
    if level < 10:
        text += f"⬆️ Следующий уровень: {next_cost} XP\n"
        if xp >= next_cost:
            text += f"✅ Ты можешь улучшить фарму! Напиши: энди улучши фарму\n"
        else:
            text += f"❌ Не хватает {next_cost - xp} XP для улучшения\n"
    else:
        text += f"⭐ МАКСИМАЛЬНЫЙ УРОВЕНЬ! ⭐\n"
    
    if last_farm:
        now = datetime.now()
        time_passed = (now - last_farm).total_seconds() / 3600
        if time_passed >= 3:
            text += f"\n✅ ФАРМА ГОТОВА! Напиши: энди фарма"
        else:
            hours_left = int(3 - time_passed)
            minutes_left = int((3 - time_passed) * 60) % 60
            text += f"\n⏳ До следующего сбора: {hours_left}ч {minutes_left}мин"
    else:
        text += f"\n✅ ФАРМА ГОТОВА! Напиши: энди фарма"
    
    return text

async def collect_farm(username: str, has_bot_in_bio: bool) -> tuple[str, str]:
    """Собирает опыт с фармы"""
    if not has_bot_in_bio:
        return f"❌ ФАРМА НЕ ДОСТУПНА!\n\nДобавь @lostearth_bot в описание профиля!", None
    
    last_farm = await get_last_farm(username)
    now = datetime.now()
    
    if last_farm:
        time_passed = (now - last_farm).total_seconds() / 3600
        if time_passed < 3:
            hours_left = int(3 - time_passed)
            minutes_left = int((3 - time_passed) * 60) % 60
            return f"⏳ Фарма ещё не готова! Приходи через {hours_left}ч {minutes_left}мин", None
    
    level = await get_farm_level(username)
    income = FARM_INCOME.get(level, 50)
    
    await update_xp(username, income)
    await update_last_farm(username)
    new_xp = await get_xp(username)
    
    return f"🏭 Ты собрал {income} XP с фармы!\n💰 Баланс: {new_xp} XP", f"Собрал {income} XP с фармы"

async def upgrade_farm_cmd(username: str, has_bot_in_bio: bool) -> tuple[str, str]:
    """Улучшает фарму"""
    if not has_bot_in_bio:
        return f"❌ ФАРМА НЕ ДОСТУПНА!\n\nДобавь @lostearth_bot в описание профиля!", None
    
    current_level = await get_farm_level(username)
    
    if current_level >= 10:
        return f"⭐ У тебя уже максимальный 10 уровень фармы!", None
    
    cost = UPGRADE_COST.get(current_level + 1, 999999)
    xp = await get_xp(username)
    
    if xp < cost:
        return f"❌ Не хватает опыта! Нужно {cost} XP, у тебя {xp} XP", None
    
    await update_xp(username, -cost)
    await update_farm_level(username, current_level + 1)
    new_level = current_level + 1
    new_income = FARM_INCOME.get(new_level, 50)
    new_xp = await get_xp(username)
    
    return f"✅ Фарма улучшена до {new_level} уровня!\n📈 Теперь приносит {new_income} XP за сбор\n💰 Баланс: {new_xp} XP", f"Улучшил фарму до {new_level} уровня"

# ========== КУБИК ==========
async def roll_dice(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = await get_xp(username)
    if xp < bet_amount:
        return f"💰 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount}", None
    if bet_amount < 50:
        return f"🎲 {username}, минимальная ставка 50 XP!", None
    
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🐱 Энди бросает кубик...")
    bot_value = await roll_dice(bot, chat_id)
    
    if player_value > bot_value:
        win_amount = bet_amount
        await update_xp(username, win_amount)
        await update_stats(username, is_win=True)
        new_xp = await get_xp(username)
        result_text = f"🎉 ПОБЕДА! 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {win_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Выиграл {win_amount} XP в кости!"
    elif player_value < bot_value:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 ПРОИГРЫШ...\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Проиграл {bet_amount} XP в кости!"
    else:
        return f"🤝 НИЧЬЯ!\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP", f"Ничья в кости! Ставка {bet_amount} XP возвращена"

# ========== ФУТБОЛ ==========
async def play_football(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="⚽")
    return msg.dice.value

async def game_football_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = await get_xp(username)
    if xp < bet_amount:
        return f"💰 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount}", None
    if bet_amount < 50:
        return f"⚽ {username}, минимальная ставка 50 XP!", None
    
    await bot.send_message(chat_id, f"⚽ {username} бьёт по воротам...")
    player_value = await play_football(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🧤 Энди защищает ворота...")
    bot_value = await play_football(bot, chat_id)
    
    player_goal = player_value >= 4
    bot_caught = bot_value >= 4
    
    if player_goal and not bot_caught:
        win_amount = bet_amount * 2
        await update_xp(username, win_amount)
        await update_stats(username, is_win=True)
        new_xp = await get_xp(username)
        result_text = f"⚽ ГОЛ! ПОБЕДА! ⚽\n\nТвой удар: {player_value}\nЭнди: {bot_value} (не поймала)\n\n✨ Ты выиграл {win_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Забил гол и выиграл {win_amount} XP в футболе!"
    elif not player_goal and bot_caught:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 ПРОМАХ...\n\nТвой удар: {player_value}\nЭнди: {bot_value} (поймала мяч)\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Промахнулся и проиграл {bet_amount} XP в футболе!"
    else:
        return f"🤝 НИЧЬЯ!\n\nТвой удар: {player_value}\nЭнди: {bot_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP", f"Ничья в футболе! Ставка {bet_amount} XP возвращена"
