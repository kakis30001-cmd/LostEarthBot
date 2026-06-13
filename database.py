import asyncpg
import os
from datetime import datetime, date

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:hgSCmLMXOyemvPATDDMerzJWtMBxFamM@postgres.railway.internal:5432/railway")

# Кэш
xp_cache = {}
stats_cache = {}
farms_cache = {}

async def init_db():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
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
        print("✅ PostgreSQL инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return False

async def get_xp(username: str) -> int:
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
    except:
        return xp_cache.get(username, 1000)

async def create_player(username: str):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("INSERT INTO players (username, xp) VALUES ($1, 1000)", username)
        await conn.close()
        xp_cache[username] = 1000
    except Exception as e:
        print(f"Ошибка создания: {e}")

async def update_xp(username: str, delta: int):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET xp = xp + $1, updated_at = NOW() WHERE username = $2", delta, username)
        await conn.close()
        if username in xp_cache:
            xp_cache[username] += delta
        else:
            xp_cache[username] = 1000 + delta
    except Exception as e:
        print(f"Ошибка обновления XP: {e}")

async def can_claim_daily_bonus(username: str) -> bool:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT last_bonus FROM players WHERE username = $1", username)
        await conn.close()
        if not row or row[0] is None:
            return True
        return row[0] < date.today()
    except:
        return True

async def claim_daily_bonus(username: str) -> int:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET xp = xp + 500, last_bonus = $1, updated_at = NOW() WHERE username = $2", date.today(), username)
        await conn.close()
        if username in xp_cache:
            xp_cache[username] += 500
        else:
            xp_cache[username] = 1500
        return 500
    except:
        return 0

async def update_stats(username: str, is_win: bool):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        if is_win:
            await conn.execute("UPDATE players SET wins = wins + 1, updated_at = NOW() WHERE username = $1", username)
        else:
            await conn.execute("UPDATE players SET losses = losses + 1, updated_at = NOW() WHERE username = $1", username)
        await conn.close()
    except Exception as e:
        print(f"Ошибка статистики: {e}")

async def get_stats(username: str) -> dict:
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
    except:
        return {"wins": 0, "losses": 0}

async def get_farms(username: str) -> dict:
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
    except:
        return {}

async def buy_farm(username: str, farm_name: str):
    farms_data = {
        "пауков": {"base_income": 50, "cost": 1000},
        "зомби": {"base_income": 75, "cost": 1000},
        "криперов": {"base_income": 100, "cost": 1000},
        "скелетов": {"base_income": 60, "cost": 1000},
        "эндерменов": {"base_income": 150, "cost": 1500},
    }
    
    if farm_name not in farms_data:
        return False, f"❌ Фермы '{farm_name}' нет!"
    
    xp = await get_xp(username)
    cost = farms_data[farm_name]["cost"]
    
    if xp < cost:
        return False, f"❌ Нужно {cost} XP, у тебя {xp} XP"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("INSERT INTO farms (username, farm_name, level, last_claim) VALUES ($1, $2, 1, NOW())", username, farm_name)
        await conn.close()
        await update_xp(username, -cost)
        if username in farms_cache:
            farms_cache[username] = await get_farms(username)
        return True, f"✅ Ферма {farm_name} куплена!"
    except Exception as e:
        return False, f"❌ Ошибка: {e}"

async def upgrade_farm(username: str, farm_name: str):
    upgrade_costs = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 5000}
    farms_data = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
    
    if farm_name not in farms_data:
        return False, f"❌ Фермы '{farm_name}' нет!"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT level FROM farms WHERE username = $1 AND farm_name = $2", username, farm_name)
        
        if not row:
            await conn.close()
            return False, f"❌ У тебя нет фермы {farm_name}!"
        
        current_level = row[0]
        if current_level >= 5:
            await conn.close()
            return False, f"⭐ Ферма уже 5 уровня!"
        
        cost = upgrade_costs[current_level + 1]
        xp = await get_xp(username)
        
        if xp < cost:
            await conn.close()
            return False, f"❌ Нужно {cost} XP для улучшения!"
        
        await conn.execute("UPDATE farms SET level = level + 1 WHERE username = $1 AND farm_name = $2", username, farm_name)
        await conn.close()
        await update_xp(username, -cost)
        
        if username in farms_cache:
            farms_cache[username] = await get_farms(username)
        
        return True, f"✅ Ферма {farm_name} улучшена до {current_level + 1} уровня!"
    except Exception as e:
        return False, f"❌ Ошибка: {e}"

async def calculate_income(username: str) -> int:
    farms = await get_farms(username)
    farms_data = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
    total = 0
    for name, data in farms.items():
        base = farms_data.get(name, 50)
        level = data.get("level", 1)
        total += base * level
    return total

async def claim_income(username: str) -> int:
    farms = await get_farms(username)
    if not farms:
        return 0
    
    farms_data = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
    now = datetime.now()
    total_income = 0
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        for name, data in farms.items():
            last_claim = data.get("last_claim")
            if last_claim:
                last_claim_time = datetime.fromtimestamp(last_claim)
                hours_passed = (now - last_claim_time).total_seconds() / 3600
                if hours_passed > 0:
                    base = farms_data.get(name, 50)
                    level = data.get("level", 1)
                    income = int(base * level * min(hours_passed, 24))
                    if income > 0:
                        total_income += income
                        await conn.execute("UPDATE farms SET last_claim = NOW() WHERE username = $1 AND farm_name = $2", username, name)
        await conn.close()
        
        if total_income > 0:
            await update_xp(username, total_income)
            if username in farms_cache:
                farms_cache[username] = await get_farms(username)
        return total_income
    except:
        return 0

async def get_leaderboard(limit: int = 10) -> list:
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
    except:
        return []
