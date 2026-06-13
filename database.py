import asyncpg
import os
from datetime import date
from typing import Optional, Dict, Any

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:hgSCmLMXOyemvPATDDMerzJWtMBxFamM@postgres.railway.internal:5432/railway")

# Кэш для быстрого доступа
xp_cache = {}
stats_cache = {}
farms_cache = {}

async def init_db():
    """Создаёт таблицы если их нет"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Таблица игроков
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                username TEXT PRIMARY KEY,
                xp INTEGER DEFAULT 1000,
                last_bonus DATE,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Таблица ферм
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                id SERIAL PRIMARY KEY,
                username TEXT REFERENCES players(username) ON DELETE CASCADE,
                farm_name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                last_claim TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(username, farm_name)
            )
        """)
        
        await conn.close()
        print("✅ PostgreSQL база данных инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

async def get_xp(username: str) -> int:
    """Получает опыт игрока"""
    if username in xp_cache:
        return xp_cache[username]
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT xp FROM players WHERE username = $1", username)
        await conn.close()
        
        if row:
            xp_cache[username] = row[0]
            return row[0]
        else:
            await create_player(username)
            return 1000
    except Exception as e:
        print(f"❌ Ошибка получения XP: {e}")
        return xp_cache.get(username, 1000)

async def create_player(username: str):
    """Создаёт нового игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO players (username, xp)
            VALUES ($1, 1000)
        """, username)
        await conn.close()
        xp_cache[username] = 1000
        print(f"✅ Создан игрок {username}")
    except Exception as e:
        print(f"❌ Ошибка создания игрока: {e}")

async def update_xp(username: str, delta: int):
    """Обновляет опыт игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE players 
            SET xp = xp + $1, updated_at = NOW()
            WHERE username = $2
        """, delta, username)
        await conn.close()
        
        if username in xp_cache:
            xp_cache[username] += delta
        else:
            xp_cache[username] = 1000 + delta
    except Exception as e:
        print(f"❌ Ошибка обновления XP: {e}")

async def can_claim_daily_bonus(username: str) -> bool:
    """Проверяет, можно ли получить ежедневный бонус"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT last_bonus FROM players WHERE username = $1", username)
        await conn.close()
        
        if not row or row[0] is None:
            return True
        return row[0] < date.today()
    except Exception as e:
        print(f"❌ Ошибка проверки бонуса: {e}")
        return True

async def claim_daily_bonus(username: str) -> int:
    """Начисляет ежедневный бонус 500 XP"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE players 
            SET xp = xp + 500, last_bonus = $1, updated_at = NOW()
            WHERE username = $2
        """, date.today(), username)
        await conn.close()
        
        if username in xp_cache:
            xp_cache[username] += 500
        else:
            xp_cache[username] = 1500
        return 500
    except Exception as e:
        print(f"❌ Ошибка начисления бонуса: {e}")
        return 0

async def update_stats(username: str, is_win: bool):
    """Обновляет статистику побед/поражений"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        if is_win:
            await conn.execute("""
                UPDATE players 
                SET wins = wins + 1, updated_at = NOW()
                WHERE username = $1
            """, username)
        else:
            await conn.execute("""
                UPDATE players 
                SET losses = losses + 1, updated_at = NOW()
                WHERE username = $1
            """, username)
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления статистики: {e}")

async def get_stats(username: str) -> dict:
    """Получает статистику игрока"""
    if username in stats_cache:
        return stats_cache[username]
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT wins, losses FROM players WHERE username = $1", username)
        await conn.close()
        
        if row:
            stats = {"wins": row[0], "losses": row[1]}
            stats_cache[username] = stats
            return stats
        return {"wins": 0, "losses": 0}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {"wins": 0, "losses": 0}

# ========== ФЕРМЫ ==========
async def get_farms(username: str) -> dict:
    """Получает фермы игрока"""
    if username in farms_cache:
        return farms_cache[username]
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("SELECT farm_name, level, last_claim FROM farms WHERE username = $1", username)
        await conn.close()
        
        farms = {}
        for row in rows:
            farms[row[0]] = {"level": row[1], "last_claim": row[2].timestamp() if row[2] else None}
        
        farms_cache[username] = farms
        return farms
    except Exception as e:
        print(f"❌ Ошибка получения ферм: {e}")
        return {}

async def buy_farm(username: str, farm_name: str):
    """Покупает ферму"""
    farms_data = {
        "пауков": {"base_income": 50, "cost": 1000},
        "зомби": {"base_income": 75, "cost": 1000},
        "криперов": {"base_income": 100, "cost": 1000},
        "скелетов": {"base_income": 60, "cost": 1000},
        "эндерменов": {"base_income": 150, "cost": 1500},
    }
    
    if farm_name not in farms_data:
        return False, f"❌ Фермы '{farm_name}' нет! Доступны: пауков, зомби, криперов, скелетов, эндерменов"
    
    xp = await get_xp(username)
    cost = farms_data[farm_name]["cost"]
    
    if xp < cost:
        return False, f"❌ Не хватает опыта! Нужно {cost} XP, у тебя {xp} XP"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO farms (username, farm_name, level, last_claim)
            VALUES ($1, $2, 1, NOW())
        """, username, farm_name)
        await conn.close()
        
        await update_xp(username, -cost)
        
        if username in farms_cache:
            farms_cache[username] = await get_farms(username)
        
        return True, f"✅ Ты купил ферму {farm_name} 1 уровня! Приносит {farms_data[farm_name]['base_income']} XP в час"
    except Exception as e:
        print(f"❌ Ошибка покупки фермы: {e}")
        return False, "❌ Ошибка при покупке фермы!"

async def upgrade_farm(username: str, farm_name: str):
    """Улучшает ферму"""
    upgrade_costs = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 5000}
    farms_data = {
        "пауков": {"base_income": 50},
        "зомби": {"base_income": 75},
        "криперов": {"base_income": 100},
        "скелетов": {"base_income": 60},
        "эндерменов": {"base_income": 150},
    }
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT level FROM farms WHERE username = $1 AND farm_name = $2", username, farm_name)
        
        if not row:
            await conn.close()
            return False, f"❌ У тебя нет фермы {farm_name}!"
        
        current_level = row[0]
        if current_level >= 5:
            await conn.close()
            return False, f"⭐ Ферма {farm_name} уже максимального 5 уровня!"
        
        cost = upgrade_costs[current_level + 1]
        xp = await get_xp(username)
        
        if xp < cost:
            await conn.close()
            return False, f"❌ Не хватает опыта! Нужно {cost} XP для улучшения до {current_level + 1} уровня"
        
        await conn.execute("""
            UPDATE farms SET level = level + 1 WHERE username = $1 AND farm_name = $2
        """, username, farm_name)
        await conn.close()
        
        await update_xp(username, -cost)
        
        if username in farms_cache:
            farms_cache[username] = await get_farms(username)
        
        new_income = farms_data[farm_name]["base_income"] * (current_level + 1)
        return True, f"✅ Ферма {farm_name} улучшена до {current_level + 1} уровня! Теперь приносит {new_income} XP в час"
    except Exception as e:
        print(f"❌ Ошибка улучшения фермы: {e}")
        return False, "❌ Ошибка при улучшении фермы!"

async def calculate_income(username: str) -> int:
    """Считает доход с ферм в час"""
    farms = await get_farms(username)
    farms_data = {
        "пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150
    }
    
    total = 0
    for farm_name, farm_data in farms.items():
        base = farms_data.get(farm_name, 50)
        level = farm_data.get("level", 1)
        total += base * level
    return total

async def claim_income(username: str) -> int:
    """Собирает накопленный опыт с ферм"""
    farms = await get_farms(username)
    if not farms:
        return 0
    
    farms_data = {
        "пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150
    }
    
    now = datetime.now()
    total_income = 0
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        for farm_name, farm_data in farms.items():
            last_claim = farm_data.get("last_claim")
            if last_claim:
                last_claim_time = datetime.fromtimestamp(last_claim)
                hours_passed = (now - last_claim_time).total_seconds() / 3600
                
                if hours_passed > 0:
                    base = farms_data.get(farm_name, 50)
                    level = farm_data.get("level", 1)
                    income = int(base * level * min(hours_passed, 24))
                    if income > 0:
                        total_income += income
                        await conn.execute("""
                            UPDATE farms SET last_claim = NOW() 
                            WHERE username = $1 AND farm_name = $2
                        """, username, farm_name)
        
        await conn.close()
        
        if total_income > 0:
            await update_xp(username, total_income)
            if username in farms_cache:
                farms_cache[username] = await get_farms(username)
        
        return total_income
    except Exception as e:
        print(f"❌ Ошибка сбора дохода: {e}")
        return 0

async def get_leaderboard(limit: int = 10) -> list:
    """Получает топ игроков по опыту"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT p.username, p.xp, p.wins, COUNT(f.id) as farms_count
            FROM players p
            LEFT JOIN farms f ON p.username = f.username
            GROUP BY p.username, p.xp, p.wins
            ORDER BY p.xp DESC
            LIMIT $1
        """, limit)
        await conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Ошибка получения топа: {e}")
        return []

# ========== СИНХРОННЫЕ ОБЁРТКИ ДЛЯ СОВМЕСТИМОСТИ ==========
import asyncio

def get_xp_sync(username: str) -> int:
    return asyncio.run(get_xp(username))

def update_xp_sync(username: str, delta: int):
    asyncio.run(update_xp(username, delta))

def can_claim_daily_bonus_sync(username: str) -> bool:
    return asyncio.run(can_claim_daily_bonus(username))

def claim_daily_bonus_sync(username: str) -> int:
    return asyncio.run(claim_daily_bonus(username))

def get_stats_sync(username: str) -> dict:
    return asyncio.run(get_stats(username))

def update_stats_sync(username: str, is_win: bool):
    asyncio.run(update_stats(username, is_win))

def get_farms_sync(username: str) -> dict:
    return asyncio.run(get_farms(username))

def buy_farm_sync(username: str, farm_name: str):
    return asyncio.run(buy_farm(username, farm_name))

def upgrade_farm_sync(username: str, farm_name: str):
    return asyncio.run(upgrade_farm(username, farm_name))

def calculate_income_sync(username: str) -> int:
    return asyncio.run(calculate_income(username))

def claim_income_sync(username: str) -> int:
    return asyncio.run(claim_income(username))

def get_leaderboard_sync(limit: int = 10) -> list:
    return asyncio.run(get_leaderboard(limit))

def init_player_sync(username: str):
    asyncio.run(create_player(username))
