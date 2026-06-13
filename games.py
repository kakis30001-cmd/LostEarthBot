import asyncio
from datetime import datetime

from database import get_xp, update_xp, update_stats, get_farm_level, update_farm_level, get_last_farm, update_last_farm

# ========== ПЛЕВОК ==========
async def add_spit(username: str, target: str) -> tuple[bool, str, int]:
    xp = await get_xp(username)
    if xp < 30:
        return False, f"у тебя всего {xp} xp нужно 30 xp для плевка", 0
    
    await update_xp(username, -30)
    new_xp = await get_xp(username)
    return True, f"💨 {username} плюнул в {target} эндер-жемчугом", new_xp

# ========== ФАРМА ==========
FARM_INCOME = {1: 50, 2: 100, 3: 200, 4: 350, 5: 550, 6: 800, 7: 1100, 8: 1500, 9: 2000, 10: 3000}
UPGRADE_COST = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 3500, 6: 5500, 7: 8000, 8: 11000, 9: 15000, 10: 20000}

async def farm_info(username: str, has_bot_in_bio: bool) -> str:
    """показывает информацию о фарме"""
    if not has_bot_in_bio:
        return f"""❌ фарма не доступна

чтобы пользоваться фармой, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 как это сделать:
1. зайди в настройки telegram
2. нажми на свою фотографию
3. выбери "редактировать профиль"
4. в разделе "описание" добавь: @lostearth_bot
5. сохрани и возвращайся

после добавления бот проверит и фарма заработает 💜"""
    
    level = await get_farm_level(username)
    income = FARM_INCOME.get(level, 50)
    next_cost = UPGRADE_COST.get(level + 1, "MAX")
    xp = await get_xp(username)
    last_farm = await get_last_farm(username)
    
    text = f"🏭 <b>твоя фарма</b> 🏭\n\n"
    text += f"📊 уровень: {level}\n"
    text += f"💰 доход за сбор: {income} xp\n"
    text += f"⏰ перезарядка: 3 часа\n"
    
    if level < 10:
        text += f"⬆️ следующий уровень: {next_cost} xp\n"
        if xp >= next_cost:
            text += f"✅ ты можешь улучшить фарму напиши: энди улучши фарму\n"
        else:
            text += f"❌ не хватает {next_cost - xp} xp для улучшения\n"
    else:
        text += f"⭐ максимальный уровень\n"
    
    if last_farm:
        now = datetime.now()
        if isinstance(last_farm, str):
            last_farm = datetime.fromisoformat(last_farm)
        time_passed = (now - last_farm).total_seconds() / 3600
        if time_passed >= 3:
            text += f"\n✅ фарма готова напиши: энди фарма"
        else:
            hours_left = int(3 - time_passed)
            minutes_left = int((3 - time_passed) * 60) % 60
            text += f"\n⏳ до следующего сбора: {hours_left}ч {minutes_left}мин"
    else:
        text += f"\n✅ фарма готова напиши: энди фарма"
    
    return text

async def collect_farm(username: str, has_bot_in_bio: bool) -> tuple[str, str]:
    """собирает опыт с фармы"""
    if not has_bot_in_bio:
        return f"""❌ фарма не доступна

добавь в описание профиля: @lostearth_bot

📝 как это сделать:
1. настройки telegram → фото профиля
2. редактировать профиль → описание
3. добавь: @lostearth_bot
4. сохрани и напиши 'энди фарма' снова

после добавления бот проверит и фарма заработает 💜""", None
    
    last_farm = await get_last_farm(username)
    now = datetime.now()
    
    if last_farm:
        if isinstance(last_farm, str):
            last_farm = datetime.fromisoformat(last_farm)
        time_passed = (now - last_farm).total_seconds() / 3600
        if time_passed < 3:
            hours_left = int(3 - time_passed)
            minutes_left = int((3 - time_passed) * 60) % 60
            return f"⏳ фарма ещё не готова приходи через {hours_left}ч {minutes_left}мин", None
    
    level = await get_farm_level(username)
    income = FARM_INCOME.get(level, 50)
    
    await update_xp(username, income)
    await update_last_farm(username)
    new_xp = await get_xp(username)
    
    return f"🏭 ты собрал {income} xp с фармы\n💰 баланс: {new_xp} xp", f"собрал {income} xp с фармы"

async def upgrade_farm_cmd(username: str, has_bot_in_bio: bool) -> tuple[str, str]:
    """улучшает фарму"""
    if not has_bot_in_bio:
        return f"""❌ фарма не доступна

добавь в описание профиля: @lostearth_bot

после добавления бот проверит и фарма заработает 💜""", None
    
    current_level = await get_farm_level(username)
    
    if current_level >= 10:
        return f"⭐ у тебя уже максимальный 10 уровень фармы", None
    
    cost = UPGRADE_COST.get(current_level + 1, 999999)
    xp = await get_xp(username)
    
    if xp < cost:
        return f"❌ не хватает опыта нужно {cost} xp у тебя {xp} xp", None
    
    await update_xp(username, -cost)
    await update_farm_level(username, current_level + 1)
    new_level = current_level + 1
    new_income = FARM_INCOME.get(new_level, 50)
    new_xp = await get_xp(username)
    
    return f"✅ фарма улучшена до {new_level} уровня\n📈 теперь приносит {new_income} xp за сбор\n💰 баланс: {new_xp} xp", f"улучшил фарму до {new_level} уровня"

# ========== КУБИК ==========
async def roll_dice(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = await get_xp(username)
    if xp < bet_amount:
        return f"💰 {username}, у тебя всего {xp} xp не хватает на ставку {bet_amount}", None
    if bet_amount < 50:
        return f"🎲 {username}, минимальная ставка 50 xp", None
    
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🐱 энди бросает кубик...")
    bot_value = await roll_dice(bot, chat_id)
    
    if player_value > bot_value:
        win_amount = bet_amount
        await update_xp(username, win_amount)
        await update_stats(username, is_win=True)
        new_xp = await get_xp(username)
        result_text = f"🎉 победа\n\nтвой кубик: {player_value}\nмой кубик: {bot_value}\n\n✨ ты выиграл {win_amount} xp\n💰 баланс: {new_xp} xp"
        return result_text, f"выиграл {win_amount} xp в кости"
    elif player_value < bot_value:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 проигрыш\n\nтвой кубик: {player_value}\nмой кубик: {bot_value}\n\n💔 ты проиграл {bet_amount} xp\n💰 баланс: {new_xp} xp"
        return result_text, f"проиграл {bet_amount} xp в кости"
    else:
        return f"🤝 ничья\n\nоба выбросили {player_value}\n\n💰 ставка возвращена\n💰 баланс: {xp} xp", f"ничья в кости ставка {bet_amount} xp возвращена"

# ========== ФУТБОЛ ==========
async def play_football(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="⚽")
    return msg.dice.value

async def game_football_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = await get_xp(username)
    if xp < bet_amount:
        return f"💰 {username}, у тебя всего {xp} xp не хватает на ставку {bet_amount}", None
    if bet_amount < 50:
        return f"⚽ {username}, минимальная ставка 50 xp", None
    
    await bot.send_message(chat_id, f"⚽ {username} бьёт по воротам...")
    player_value = await play_football(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🧤 энди защищает ворота...")
    bot_value = await play_football(bot, chat_id)
    
    player_goal = player_value >= 4
    bot_caught = bot_value >= 4
    
    if player_goal and not bot_caught:
        win_amount = bet_amount * 2
        await update_xp(username, win_amount)
        await update_stats(username, is_win=True)
        new_xp = await get_xp(username)
        result_text = f"⚽ гол победа\n\nтвой удар: {player_value}\nэнди: {bot_value} (не поймала)\n\n✨ ты выиграл {win_amount} xp\n💰 баланс: {new_xp} xp"
        return result_text, f"забил гол и выиграл {win_amount} xp"
    elif not player_goal and bot_caught:
        await update_xp(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_xp = await get_xp(username)
        result_text = f"😔 промах\n\nтвой удар: {player_value}\nэнди: {bot_value} (поймала)\n\n💔 ты проиграл {bet_amount} xp\n💰 баланс: {new_xp} xp"
        return result_text, f"промахнулся и проиграл {bet_amount} xp"
    else:
        return f"🤝 ничья\n\nтвой удар: {player_value}\nэнди: {bot_value}\n\n💰 ставка возвращена\n💰 баланс: {xp} xp", f"ничья ставка {bet_amount} xp возвращена"
