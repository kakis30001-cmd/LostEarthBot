import asyncpg
import os
from datetime import datetime, date

# Берём переменные ТОЛЬКО из окружения Railway
DB_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL", "")
DB_URL = os.getenv("DATABASE_URL", "")

# Альтернативно, собираем из отдельных переменных
PGHOST = os.getenv("PGHOST", "")
PGPORT = os.getenv("PGPORT", "5432")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")
PGDATABASE = os.getenv("PGDATABASE", "railway")

# Показываем параметры для отладки
print(f"🔍 Параметры подключения:")
print(f"   DATABASE_URL: {DB_URL[:50] if DB_URL else 'None'}...")
print(f"   DATABASE_PUBLIC_URL: {DB_PUBLIC_URL[:50] if DB_PUBLIC_URL else 'None'}...")
print(f"   PGHOST: {PGHOST}")
print(f"   PGPASSWORD: {'***' if PGPASSWORD else 'None'}")
print(f"   PGPORT: {PGPORT}")

pool = None

async def connect_db():
    global pool
    print("🔌 Подключение к БД...")
    
    # Пробуем через DATABASE_URL (внутренний)
    if DB_URL:
        try:
            print("   Пробую через DATABASE_URL...")
            pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5, timeout=15)
            
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
                
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_level INTEGER DEFAULT 1")
                except:
                    pass
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS last_farm TIMESTAMP DEFAULT NULL")
                except:
                    pass
                
            print("✅ PostgreSQL подключена через DATABASE_URL")
            return True
        except Exception as e:
            print(f"❌ Ошибка через DATABASE_URL: {e}")
    
    # Пробуем через DATABASE_PUBLIC_URL
    if DB_PUBLIC_URL:
        try:
            print("   Пробую через DATABASE_PUBLIC_URL...")
            pool = await asyncpg.create_pool(DB_PUBLIC_URL, min_size=1, max_size=5, timeout=15)
            
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
                
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_level INTEGER DEFAULT 1")
                except:
                    pass
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS last_farm TIMESTAMP DEFAULT NULL")
                except:
                    pass
                
            print("✅ PostgreSQL подключена через DATABASE_PUBLIC_URL")
            return True
        except Exception as e:
            print(f"❌ Ошибка через DATABASE_PUBLIC_URL: {e}")
    
    # Пробуем собрать URL из отдельных переменных
    if PGHOST and PGPASSWORD:
        try:
            manual_url = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
            print(f"   Пробую ручной URL: postgresql://{PGUSER}:***@{PGHOST}:{PGPORT}/{PGDATABASE}")
            pool = await asyncpg.create_pool(manual_url, min_size=1, max_size=5, timeout=15)
            
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
                
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_level INTEGER DEFAULT 1")
                except:
                    pass
                try:
                    await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS last_farm TIMESTAMP DEFAULT NULL")
                except:
                    pass
                
            print("✅ PostgreSQL подключена через ручной URL")
            return True
        except Exception as e:
            print(f"❌ Ошибка через ручной URL: {e}")
    
    print("❌ Не удалось подключиться к БД ни одним способом")
    return False

async def init_db():
    return await connect_db()

async def get_xp(username: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT xp FROM players WHERE username = $1", username)
        if row:
            return row["xp"]
        else:
            await create_player(username)
            return 1000

async def create_player(username: str):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO players (username, xp) VALUES ($1, 1000) ON CONFLICT (username) DO NOTHING", username)

async def update_xp(username: str, delta: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET xp = xp + $1, updated_at = NOW() WHERE username = $2", delta, username)

async def can_claim_daily_bonus(username: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_bonus FROM players WHERE username = $1", username)
        if not row or row["last_bonus"] is None:
            return True
        return row["last_bonus"] < date.today()

async def claim_daily_bonus(username: str) -> int:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET xp = xp + 500, last_bonus = $1, updated_at = NOW() WHERE username = $2", date.today(), username)
        return 500

async def update_stats(username: str, is_win: bool):
    async with pool.acquire() as conn:
        if is_win:
            await conn.execute("UPDATE players SET wins = wins + 1, updated_at = NOW() WHERE username = $1", username)
        else:
            await conn.execute("UPDATE players SET losses = losses + 1, updated_at = NOW() WHERE username = $1", username)

async def get_stats(username: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT wins, losses FROM players WHERE username = $1", username)
        if row:
            return {"wins": row["wins"], "losses": row["losses"]}
        return {"wins": 0, "losses": 0}

async def get_farm_level(username: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT farm_level FROM players WHERE username = $1", username)
        if row:
            return row["farm_level"]
        return 1

async def update_farm_level(username: str, new_level: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET farm_level = $1, updated_at = NOW() WHERE username = $2", new_level, username)

async def get_last_farm(username: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_farm FROM players WHERE username = $1", username)
        if row and row["last_farm"]:
            return row["last_farm"]
        return None

async def update_last_farm(username: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET last_farm = NOW() WHERE username = $1", username)

async def get_leaderboard(limit: int = 10) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT username, xp, wins, losses, farm_level
            FROM players
            ORDER BY xp DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
