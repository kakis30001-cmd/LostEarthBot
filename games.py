import os
import json
import re
import asyncio
from datetime import datetime, date

# ========== ФАЙЛОВОЕ ХРАНИЛИЩЕ ==========
PLAYERS_FILE = "players.json"

FARMS = {
    "пауков": {"base_income": 50, "emoji": "🕷️", "cost": 1000},
    "зомби": {"base_income": 75, "emoji": "🧟", "cost": 1000},
    "криперов": {"base_income": 100, "emoji": "💥", "cost": 1000},
    "скелетов": {"base_income": 60, "emoji": "🏹", "cost": 1000},
    "эндерменов": {"base_income": 150, "emoji": "👾", "cost": 1500},
}

UPGRADE_COSTS = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 5000}

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
            "farms": {},
            "last_claim": datetime.now().timestamp()
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

# ========== ПЛЕВОК ==========
def add_spit(username: str, target: str) -> tuple[bool, str, int]:
    xp = get_xp(username)
    if xp < 30:
        return False, f"У тебя всего {xp} XP! Нужно 30 XP для плевка!", 0
    
    update_xp(username, -30)
    new_xp = get_xp(username)
    return True, f"💨 {username} плюнул(а) в {target} эндер-жемчугом!", new_xp

# ========== ФЕРМЫ ==========
def get_farms(username: str) -> dict:
    data = load_players()
    if username not in data:
        init_player(username)
    return data[username].get("farms", {})

def buy_farm(username: str, farm_name: str):
    if farm_name not in FARMS:
        return False, f"❌ Фермы '{farm_name}' нет! Доступны: пауков, зомби, криперов, скелетов, эндерменов"
    
    farms = get_farms(username)
    if farm_name in farms:
        return False, f"❌ У тебя уже есть ферма {farm_name}!"
    
    cost = FARMS[farm_name]["cost"]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"❌ Не хватает опыта! Нужно {cost} XP, у тебя {xp} XP"
    
    update_xp(username, -cost)
    farms[farm_name] = {"level": 1, "last_claim": datetime.now().timestamp()}
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    return True, f"✅ Ты купил ферму {farm_name} 1 уровня! Приносит {FARMS[farm_name]['base_income']} XP в час"

def upgrade_farm(username: str, farm_name: str):
    farms = get_farms(username)
    if farm_name not in farms:
        return False, f"❌ У тебя нет фермы {farm_name}!"
    
    current_level = farms[farm_name]["level"]
    if current_level >= 5:
        return False, f"⭐ Ферма {farm_name} уже максимального 5 уровня!"
    
    cost = UPGRADE_COSTS[current_level + 1]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"❌ Не хватает опыта! Нужно {cost} XP для улучшения до {current_level + 1} уровня"
    
    update_xp(username, -cost)
    farms[farm_name]["level"] = current_level + 1
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    new_income = FARMS[farm_name]["base_income"] * (current_level + 1)
    return True, f"✅ Ферма {farm_name} улучшена до {current_level + 1} уровня! Теперь приносит {new_income} XP в час"

def calculate_income(farms: dict) -> int:
    total = 0
    for farm_name, farm_data in farms.items():
        if farm_name in FARMS:
            base = FARMS[farm_name]["base_income"]
            level = farm_data.get("level", 1)
            total += base * level
    return total

def claim_income(username: str) -> int:
    farms = get_farms(username)
    if not farms:
        return 0
    
    now = datetime.now()
    total_income = 0
    
    data = load_players()
    for farm_name, farm_data in farms.items():
        last_claim = farm_data.get("last_claim")
        if isinstance(last_claim, str):
            last_claim = float(last_claim)
        last_claim_time = datetime.fromtimestamp(last_claim)
        hours_passed = (now - last_claim_time).total_seconds() / 3600
        
        if hours_passed > 0:
            base = FARMS[farm_name]["base_income"]
            level = farm_data.get("level", 1)
            income = int(base * level * min(hours_passed, 24))
            if income > 0:
                total_income += income
                farm_data["last_claim"] = now.timestamp()
    
    if total_income > 0:
        update_xp(username, total_income)
        data[username]["farms"] = farms
        save_players(data)
    
    return total_income

def get_leaderboard(limit: int = 10) -> list:
    data = load_players()
    players = []
    for username, info in data.items():
        players.append({
            "username": username,
            "xp": info.get("xp", 0),
            "wins": info.get("wins", 0),
            "farms_count": len(info.get("farms", {}))
        })
    players.sort(key=lambda x: x["xp"], reverse=True)
    return players[:limit]

# ========== ИГРЫ ==========
async def roll_dice(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def play_football(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="⚽")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = get_xp(username)
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
        update_xp(username, win_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        result_text = f"🎉 ПОБЕДА! 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {win_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Выиграл {win_amount} XP в кости!"
    elif player_value < bot_value:
        update_xp(username, -bet_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        result_text = f"😔 ПРОИГРЫШ...\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Проиграл {bet_amount} XP в кости!"
    else:
        result_text = f"🤝 НИЧЬЯ!\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP"
        return result_text, f"Ничья в кости! Ставка {bet_amount} XP возвращена"

async def game_football_bet(username: str, bet_amount: int, bot, chat_id: int) -> tuple[str, str]:
    xp = get_xp(username)
    if xp < bet_amount:
        return f"💰 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount}", None
    if bet_amount < 50:
        return f"⚽ {username}, минимальная ставка 50 XP!", None
    
    await bot.send_message(chat_id, f"⚽ {username} бьёт по воротам...")
    player_value = await play_football(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🧤 Энди защищает ворота...")
    bot_value = await play_football(bot, chat_id)
    
    # Футбол: 1-2-3 = промах (Энди поймала), 4-5-6 = гол (Энди не поймала)
    player_goal = player_value >= 4
    bot_caught = bot_value >= 4
    
    if player_goal and not bot_caught:
        # Гол! Энди не поймала - выигрыш x2
        win_amount = bet_amount * 2
        update_xp(username, win_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        result_text = f"⚽ ГОЛ! ПОБЕДА! ⚽\n\nТвой удар: {player_value}\nЭнди: {bot_value} (не поймала)\n\n✨ Ты забил гол и выиграл {win_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Забил гол и выиграл {win_amount} XP в футболе!"
    elif not player_goal and bot_caught:
        # Промах, Энди поймала - проигрыш
        update_xp(username, -bet_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        result_text = f"😔 ПРОМАХ...\n\nТвой удар: {player_value}\nЭнди: {bot_value} (поймала мяч)\n\n💔 Ты промахнулся и проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP"
        return result_text, f"Промахнулся и проиграл {bet_amount} XP в футболе!"
    else:
        # Ничья или вратарь не поймал но игрок не забил
        result_text = f"🤝 НИЧЬЯ!\n\nТвой удар: {player_value}\nЭнди: {bot_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP"
        return result_text, f"Ничья в футболе! Ставка {bet_amount} XP возвращена"
