import os
import json
from datetime import date
from typing import Optional, Dict, Any

PLAYERS_FILE = "players.json"

def load_players():
    """Загружает всех игроков из файла"""
    if not os.path.exists(PLAYERS_FILE):
        return {}
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_players(data):
    """Сохраняет игроков в файл"""
    try:
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

async def get_balance(username: str) -> int:
    """Получает баланс игрока"""
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        save_players(data)
    return data[username].get("balance", 100)

async def create_player(username: str):
    """Создаёт нового игрока"""
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        save_players(data)

async def update_balance(username: str, delta: int):
    """Обновляет баланс игрока"""
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["balance"] = data[username].get("balance", 100) + delta
    save_players(data)

async def can_claim_daily_bonus(username: str) -> bool:
    """Проверяет, можно ли получить ежедневный бонус"""
    data = load_players()
    if username not in data:
        return True
    last_bonus = data[username].get("last_bonus")
    if not last_bonus:
        return True
    return last_bonus != str(date.today())

async def claim_daily_bonus(username: str) -> int:
    """Начисляет ежедневный бонус 100 алмазов"""
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["balance"] = data[username].get("balance", 100) + 100
    data[username]["last_bonus"] = str(date.today())
    save_players(data)
    return 100

async def update_stats(username: str, is_win: bool):
    """Обновляет статистику побед/поражений"""
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    if is_win:
        data[username]["wins"] = data[username].get("wins", 0) + 1
    else:
        data[username]["losses"] = data[username].get("losses", 0) + 1
    save_players(data)

async def get_stats(username: str) -> dict:
    """Получает статистику игрока"""
    data = load_players()
    if username not in data:
        return {"wins": 0, "losses": 0}
    return {"wins": data[username].get("wins", 0), "losses": data[username].get("losses", 0)}

async def get_top_players(limit: int = 10) -> list:
    """Получает топ игроков по балансу"""
    data = load_players()
    players = []
    for username, info in data.items():
        players.append({
            "username": username,
            "balance": info.get("balance", 0),
            "wins": info.get("wins", 0),
            "losses": info.get("losses", 0)
        })
    players.sort(key=lambda x: x["balance"], reverse=True)
    return players[:limit]

# Синхронные версии для совместимости с существующим кодом
def get_balance_sync(username: str) -> int:
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        save_players(data)
    return data[username].get("balance", 100)

def update_balance_sync(username: str, delta: int):
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["balance"] = data[username].get("balance", 100) + delta
    save_players(data)

def update_stats_sync(username: str, is_win: bool):
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    if is_win:
        data[username]["wins"] = data[username].get("wins", 0) + 1
    else:
        data[username]["losses"] = data[username].get("losses", 0) + 1
    save_players(data)

def get_stats_sync(username: str) -> dict:
    data = load_players()
    if username not in data:
        return {"wins": 0, "losses": 0}
    return {"wins": data[username].get("wins", 0), "losses": data[username].get("losses", 0)}
