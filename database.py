import asyncpg
import os
from datetime import datetime, date

DATABASE_URL = os.environ.get("DATABASE_URL")

pool = None

async def connect_db():
    global pool
    print(f"🔍 DATABASE_URL exists: {DATABASE_URL is not None}")
    
    if not DATABASE_URL:
        print("❌ НЕТ ПЕРЕМЕННОЙ DATABASE_URL")
        return False
    
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        
        async with pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS players(
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
            
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                is_bot BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS andy_dialogs(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                user_message TEXT,
                andy_response TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_stats(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                messages_count INTEGER DEFAULT 0,
                last_message TIMESTAMP,
                UNIQUE(username)
            )
            """)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_username ON chat_history(username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_andy_dialogs_username ON andy_dialogs(username)")
            
        print("✅ PostgreSQL подключена!")
        return True
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return False

async def get_pool():
    return pool

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
async def get_xp(username: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT xp FROM players WHERE username = $1", username)
        if row:
            return row["xp"]
        await create_player(username)
        return 1000

async def create_player(username: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO players (username, xp) VALUES ($1, 1000) 
            ON CONFLICT (username) DO NOTHING
        """, username)

async def update_xp(username: str, delta: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE players SET xp = xp + $1, updated_at = NOW() 
            WHERE username = $2
        """, delta, username)

async def can_claim_daily_bonus(username: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_bonus FROM players WHERE username = $1", username)
        if not row or row["last_bonus"] is None:
            return True
        return row["last_bonus"] < date.today()

async def claim_daily_bonus(username: str) -> int:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE players SET xp = xp + 500, last_bonus = $1, updated_at = NOW() 
            WHERE username = $2
        """, date.today(), username)
        return 500

async def update_stats(username: str, is_win: bool):
    async with pool.acquire() as conn:
        if is_win:
            await conn.execute("UPDATE players SET wins = wins + 1 WHERE username = $1", username)
        else:
            await conn.execute("UPDATE players SET losses = losses + 1 WHERE username = $1", username)

async def get_stats(username: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT wins, losses FROM players WHERE username = $1", username)
        if row:
            return {"wins": row["wins"], "losses": row["losses"]}
        return {"wins": 0, "losses": 0}

# ========== ФУНКЦИИ ФАРМЫ ==========
async def get_farm_level(username: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT farm_level FROM players WHERE username = $1", username)
        return row["farm_level"] if row else 1

async def update_farm_level(username: str, new_level: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET farm_level = $1 WHERE username = $2", new_level, username)

async def get_last_farm(username: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_farm FROM players WHERE username = $1", username)
        return row["last_farm"] if row else None

async def update_last_farm(username: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET last_farm = NOW() WHERE username = $1", username)

# ========== ФУНКЦИИ ИСТОРИИ ==========
async def save_chat_message(username: str, message: str, is_bot: bool = False):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO chat_history (username, message, is_bot) VALUES ($1, $2, $3)
        """, username, message, is_bot)

async def save_andy_dialog(username: str, user_message: str, andy_response: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO andy_dialogs (username, user_message, andy_response) VALUES ($1, $2, $3)
        """, username, user_message, andy_response)

async def get_chat_history(limit: int = 50) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT username, message, is_bot, created_at 
            FROM chat_history ORDER BY created_at DESC LIMIT $1
        """, limit)
        return [dict(row) for row in rows]

# ========== ТОП ИГРОКОВ ==========
async def get_leaderboard(limit: int = 10) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT username, xp, wins, losses, farm_level
            FROM players ORDER BY xp DESC LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
