import asyncio
from datetime import datetime

from database import get_xp, update_xp, update_stats, get_farm_level, update_farm_level, get_last_farm, update_last_farm

FARM_INCOME = {1: 50, 2: 100, 3: 200, 4: 350, 5: 550, 6: 800, 7: 1100, 8: 1500, 9: 2000, 10: 3000}
UPGRADE_COST = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 3500, 6: 5500, 7: 8000, 8: 11000, 9: 15000, 10: 20000}

# ========== ПЛЕВОК ==========
async def add_spit(username: str, target: str) -> tuple[bool, str, int]:
    xp = await get_xp(username)
    if xp < 30:
        return False, f"у тебя всего {xp} xp нужно 30 xp для плевка", 0
    
    await update_xp(username, -30)
    new_xp = await get_xp(username)
    return True, f"💨 {username} плюнул в {target} эндер-жемчугом", new_xp

# ========== ФАРМА ==========
async def farm_info(username: str, has_bot_in_bio: bool, is_subscribed: bool = False) -> str:
    if not is_subscribed or not has_bot_in_bio:
        return f"""❌ <b>ФАРМА НЕ ДОСТУПНА</b>

<b>Требования для доступа к фарме:</b>

1️⃣ {'✅' if is_subscribed else '❌'} <b>Подписка на канал:</b> @LostEarthSMP
   {'✅ Вы подписаны' if is_subscribed else '❌ Вы НЕ подписаны'}

2️⃣ {'✅' if has_bot_in_bio else '❌'} <b>Описание профиля:</b> @lostearth_bot
   {'✅ Найдено в описании' if has_bot_in_bio else '❌ Не найдено'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📝 Как исправить:</b>

🔹 <b>Подписаться на канал:</b>
👉 https://t.me/LostEarthSMP

🔹 <b>Добавить в описание профиля:</b>
• Настройки Telegram → Редактировать профиль
• В поле "Описание" добавь: @lostearth_bot
• Сохрани изменения

После выполнения напиши /check для проверки ✅"""
    
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
        text += f"⭐ МАКСИМАЛЬНЫЙ УРОВЕНЬ!\n"
    
    if last_farm:
        now = datetime.now()
        if isinstance(last_farm, str):
            last_farm = datetime.fromisoformat(last_farm)
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

async def collect_farm(username: str, has_bot_in_bio: bool, is_subscribed: bool = False) -> tuple[str, str]:
    if not is_subscribed or not has_bot_in_bio:
        missing = []
        if not is_subscribed:
            missing.append("• Подпишись на канал: https://t.me/LostEarthSMP")
        if not has_bot_in_bio:
            missing.append("• Добавь в описание профиля: @lostearth_bot")
        
        return f"""❌ <b>ФАРМА НЕ ДОСТУПНА</b>

<b>Чтобы собирать опыт с фармы, нужно:</b>

{chr(10).join(missing)}

<b>📝 Как добавить в описание:</b>
1. Настройки Telegram → Редактировать профиль
2. В поле "Описание" добавь: @lostearth_bot
3. Сохрани изменения

После выполнения напиши /check для проверки ✅""", None
    
    last_farm = await get_last_farm(username)
    now = datetime.now()
    
    if last_farm:
        if isinstance(last_farm, str):
            last_farm = datetime.fromisoformat(last_farm)
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
    
    return f"🏭 Ты собрал {income} XP с фармы!\n💰 Баланс: {new_xp} XP", f"собрал {income} XP с фармы"

async def upgrade_farm_cmd(username: str, has_bot_in_bio: bool, is_subscribed: bool = False) -> tuple[str, str]:
    if not is_subscribed or not has_bot_in_bio:
        missing = []
        if not is_subscribed:
            missing.append("• Подпишись на канал: https://t.me/LostEarthSMP")
        if not has_bot_in_bio:
            missing.append("• Добавь в описание профиля: @lostearth_bot")
        
        return f"""❌ <b>УЛУЧШЕНИЕ ФАРМЫ НЕ ДОСТУПНО</b>

<b>Чтобы улучшать фарму, нужно:</b>

{chr(10).join(missing)}

После выполнения напиши /check для проверки ✅""", None
    
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
    
    return f"✅ Фарма улучшена до {new_level} уровня!\n📈 Теперь приносит {new_income} XP за сбор\n💰 Баланс: {new_xp} XP", f"улучшил фарму до {new_level} уровня"

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
    if bet_amount > 5000:
        return f"🎲 {username}, максимальная ставка 5000 XP!", None
    
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
        return result_text, f"выиграл {win_amount} XP в кости!"
    elif player_value < bot_value:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 ПРОИГРЫШ...\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"проиграл {bet_amount} XP в кости!"
    else:
        return f"🤝 НИЧЬЯ!\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP", f"ничья в кости! ставка {bet_amount} XP возвращена"

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
    if bet_amount > 5000:
        return f"⚽ {username}, максимальная ставка 5000 XP!", None
    
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
        return result_text, f"забил гол и выиграл {win_amount} XP!"
    elif not player_goal and bot_caught:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 ПРОМАХ...\n\nТвой удар: {player_value}\nЭнди: {bot_value} (поймала)\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"промахнулся и проиграл {bet_amount} XP!"
    else:
        return f"🤝 НИЧЬЯ!\n\nТвой удар: {player_value}\nЭнди: {bot_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP", f"ничья! ставка {bet_amount} XP возвращена"
