import os
import json
import re
import asyncio
import random
from datetime import datetime, date, timedelta

# ========== ФАЙЛОВОЕ ХРАНИЛИЩЕ ==========
PLAYERS_FILE = "players.json"

# Новая система ферм - одна ферма которая прокачивается
FARM_LEVELS = {
    1: {"income": 50, "upgrade_cost": 500, "upgrade_hours": 2},
    2: {"income": 100, "upgrade_cost": 1000, "upgrade_hours": 4},
    3: {"income": 200, "upgrade_cost": 2000, "upgrade_hours": 8},
    4: {"income": 400, "upgrade_cost": 4000, "upgrade_hours": 16},
    5: {"income": 800, "upgrade_cost": 8000, "upgrade_hours": 24},
    6: {"income": 1600, "upgrade_cost": 16000, "upgrade_hours": 48},
    7: {"income": 3200, "upgrade_cost": 32000, "upgrade_hours": 72},
    8: {"income": 6400, "upgrade_cost": 64000, "upgrade_hours": 96},
    9: {"income": 12800, "upgrade_cost": 128000, "upgrade_hours": 120},
    10: {"income": 25600, "upgrade_cost": 0, "upgrade_hours": 0},
}

SPIT_COST = 10

def load_players():
    if not os.path.exists(PLAYERS_FILE):
        return {}
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_players(data):
    try:
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def init_player(username: str):
    data = load_players()
    if username not in data:
        data[username] = {
            "xp": 1000,
            "last_bonus": None,
            "wins": 0,
            "losses": 0,
            "farm_level": 1,
            "farm_last_claim": datetime.now().timestamp(),
            "farm_upgrade_start": None,
        }
        save_players(data)

def get_xp(username: str) -> int:
    data = load_players()
    if username not in data:
        init_player(username)
        return 1000
    return data[username].get("xp", 1000)

def update_xp(username: str, delta: int):
    data = load_players()
    if username not in data:
        init_player(username)
    data[username]["xp"] = data[username].get("xp", 1000) + delta
    save_players(data)

def get_stats(username: str) -> dict:
    data = load_players()
    if username not in data:
        return {"wins": 0, "losses": 0}
    return {"wins": data[username].get("wins", 0), "losses": data[username].get("losses", 0)}

def update_stats(username: str, is_win: bool):
    data = load_players()
    if username not in data:
        init_player(username)
    if is_win:
        data[username]["wins"] = data[username].get("wins", 0) + 1
    else:
        data[username]["losses"] = data[username].get("losses", 0) + 1
    save_players(data)

def can_claim_daily_bonus(username: str) -> bool:
    data = load_players()
    if username not in data:
        return True
    last_bonus = data[username].get("last_bonus")
    if not last_bonus:
        return True
    return last_bonus != str(date.today())

def claim_daily_bonus(username: str) -> int:
    data = load_players()
    if username not in data:
        init_player(username)
    data[username]["xp"] = data[username].get("xp", 1000) + 500
    data[username]["last_bonus"] = str(date.today())
    save_players(data)
    return 500

# ========== НОВАЯ СИСТЕМА ФЕРМ ==========
def get_farm_level(username: str) -> int:
    data = load_players()
    if username not in data:
        init_player(username)
        return 1
    return data[username].get("farm_level", 1)

def get_farm_info(username: str):
    """Полная информация о ферме"""
    data = load_players()
    if username not in data:
        init_player(username)
    
    level = data[username].get("farm_level", 1)
    income = FARM_LEVELS[level]["income"]
    upgrade_start = data[username].get("farm_upgrade_start")
    
    upgrading = False
    upgrade_remaining = None
    upgrade_complete_level = None
    
    if upgrade_start:
        upgrade_start_time = datetime.fromtimestamp(upgrade_start)
        if level < 10:
            upgrade_hours = FARM_LEVELS[level]["upgrade_hours"]
            finish_time = upgrade_start_time + timedelta(hours=upgrade_hours)
            if datetime.now() >= finish_time:
                # Завершаем улучшение
                new_level = level + 1
                data[username]["farm_level"] = new_level
                data[username]["farm_upgrade_start"] = None
                save_players(data)
                level = new_level
                income = FARM_LEVELS[level]["income"]
            else:
                upgrading = True
                remaining = finish_time - datetime.now()
                upgrade_remaining = remaining.total_seconds() / 3600
                upgrade_complete_level = level + 1
    
    next_upgrade = None
    if level < 10 and not upgrading:
        next_upgrade = {
            "level": level + 1,
            "cost": FARM_LEVELS[level]["upgrade_cost"],
            "hours": FARM_LEVELS[level]["upgrade_hours"],
            "income": FARM_LEVELS[level + 1]["income"]
        }
    
    return {
        "level": level,
        "income_per_hour": income,
        "upgrading": upgrading,
        "upgrade_remaining_hours": upgrade_remaining,
        "upgrade_complete_level": upgrade_complete_level,
        "next_upgrade": next_upgrade,
        "is_max": level >= 10
    }

def start_farm_upgrade(username: str):
    """Начинает улучшение фермы"""
    data = load_players()
    if username not in data:
        init_player(username)
    
    current_level = data[username].get("farm_level", 1)
    if current_level >= 10:
        return False, "Ферма уже максимального 10 уровня! 🏆"
    
    if data[username].get("farm_upgrade_start"):
        return False, "Улучшение уже запущено! Подожди... ⏳"
    
    cost = FARM_LEVELS[current_level]["upgrade_cost"]
    xp = data[username].get("xp", 1000)
    
    if xp < cost:
        return False, f"Не хватает XP! Нужно {cost} XP для улучшения до {current_level + 1} уровня 💔"
    
    update_xp(username, -cost)
    data[username]["farm_upgrade_start"] = datetime.now().timestamp()
    save_players(data)
    
    hours = FARM_LEVELS[current_level]["upgrade_hours"]
    return True, f"Улучшение фермы до {current_level + 1} уровня началось! 🚀 Закончится через {hours} часов"

def claim_farm_income(username: str):
    """Собирает доход с фермы (раз в час максимум)"""
    data = load_players()
    if username not in data:
        init_player(username)
        return 0, 0, None
    
    # Проверяем завершение улучшения (обновляем статус)
    farm_info = get_farm_info(username)
    
    last_claim = data[username].get("farm_last_claim", datetime.now().timestamp())
    if isinstance(last_claim, str):
        last_claim = float(last_claim)
    last_claim_time = datetime.fromtimestamp(last_claim)
    
    # Сколько часов прошло с последнего сбора
    hours_passed = (datetime.now() - last_claim_time).total_seconds() / 3600
    
    # Можно собирать если прошёл хотя бы 1 час
    if hours_passed < 1:
        return 0, hours_passed, farm_info
    
    # Сколько часов забираем (максимум 24 чтобы не накапливалось слишком много)
    hours_to_claim = min(hours_passed, 24)
    
    level = data[username].get("farm_level", 1)
    income_per_hour = FARM_LEVELS[level]["income"]
    total_income = int(income_per_hour * hours_to_claim)
    
    if total_income > 0:
        data[username]["xp"] = data[username].get("xp", 1000) + total_income
        data[username]["farm_last_claim"] = datetime.now().timestamp()
        save_players(data)
    
    return total_income, hours_passed, farm_info

def get_leaderboard(limit: int = 10) -> list:
    data = load_players()
    players = []
    for username, info in data.items():
        players.append({
            "username": username,
            "xp": info.get("xp", 0),
            "wins": info.get("wins", 0),
            "farm_level": info.get("farm_level", 1)
        })
    players.sort(key=lambda x: x["xp"], reverse=True)
    return players[:limit]

# ========== ИГРА В КОСТИ ==========
async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bot, chat_id: int, bet_amount: int = 50) -> str:
    """Игра в кости с генерацией результата"""
    xp = get_xp(username)
    
    if bet_amount < 10:
        return f"🎲 Минимальная ставка 10 XP! 😲"
    
    if xp < bet_amount:
        return f"💔 У тебя всего {xp} XP! Не хватает на ставку {bet_amount} 😲"
    
    # Анимация бросков
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🐱 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    # Результат
    if player_value > bot_value:
        win_amount = bet_amount
        update_xp(username, win_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        return f"""🎉 <b>ПОБЕДА!</b> 🎉

🎲 Твой кубик: {player_value}
🐱 Мой кубик: {bot_value}

✨ Ты выиграл {win_amount} XP!
💰 Баланс: {new_xp} XP 💜"""
    
    elif player_value < bot_value:
        lose_amount = bet_amount
        update_xp(username, -lose_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        return f"""😔 <b>ПРОИГРЫШ...</b> 😔

🎲 Твой кубик: {player_value}
🐱 Мой кубик: {bot_value}

💔 Ты проиграл {lose_amount} XP!
💰 Баланс: {new_xp} XP 😲"""
    
    else:
        return f"""🤝 <b>НИЧЬЯ!</b> 🤝

🎲 Твой кубик: {player_value}
🐱 Мой кубик: {bot_value}

💰 Ставка возвращена!
💰 Баланс: {xp} XP 🎮"""
