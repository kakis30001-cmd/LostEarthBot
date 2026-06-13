import asyncpg
import os
from datetime import datetime, date

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:hgSCmLMXOyemvPATDDMerzJWtMBxFamM@postgres.railway.internal:5432/railway")

# Кэш
xp_cache = {}
stats_cache = {}

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
                farm_level INTEGER DEFAULT 1,
                last_farm TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
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

async def get_farm_level(username: str) -> int:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT farm_level FROM players WHERE username = $1", username)
        await conn.close()
        if row:
            return row[0]
        return 1
    except:
        return 1

async def update_farm_level(username: str, new_level: int):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET farm_level = $1, updated_at = NOW() WHERE username = $2", new_level, username)
        await conn.close()
    except Exception as e:
        print(f"Ошибка обновления уровня фармы: {e}")

async def get_last_farm(username: str):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT last_farm FROM players WHERE username = $1", username)
        await conn.close()
        if row and row[0]:
            return row[0]
        return None
    except:
        return None

async def update_last_farm(username: str):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET last_farm = NOW() WHERE username = $1", username)
        await conn.close()
    except Exception as e:
        print(f"Ошибка обновления времени фармы: {e}")

async def get_leaderboard(limit: int = 10) -> list:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT username, xp, wins, losses, farm_level
            FROM players
            ORDER BY xp DESC
            LIMIT $1
        """, limit)
        await conn.close()
        return [dict(row) for row in rows]
    except:
        return []
