import asyncpg
import os
from datetime import datetime, date

# Берем переменные из окружения Railway (из твоего скриншота)
DB_HOST = os.getenv("PGHOST", "postgres.railway.internal")
DB_PORT = os.getenv("PGPORT", "5432")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "GvVgH0wThbxIW0ruuQkDsZVVYpuzrMgdt")  # Берем из скриншота
DB_NAME = os.getenv("PGDATABASE", "railway")

# Собираем URL из переменных
DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Публичный URL для внешнего подключения
PUBLIC_HOST = "thomas.proxy.rlwy.net"
PUBLIC_PORT = "37739"
PUBLIC_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{PUBLIC_HOST}:{PUBLIC_PORT}/{DB_NAME}"

print(f"🔍 Параметры БД:")
print(f"   Хост: {DB_HOST}")
print(f"   Порт: {DB_PORT}")
print(f"   Пользователь: {DB_USER}")
print(f"   База: {DB_NAME}")
print(f"   URL: {DB_URL.replace(DB_PASSWORD, '***')}")

pool = None

async def connect_db():
    global pool
    try:
        print("🔌 Подключение через внутренний URL...")
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
            
            # Добавляем колонки если их нет
            try:
                await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_level INTEGER DEFAULT 1")
            except Exception as e:
                print(f"   Колонка farm_level уже есть или ошибка: {e}")
            try:
                await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS last_farm TIMESTAMP DEFAULT NULL")
            except Exception as e:
                print(f"   Колонка last_farm уже есть или ошибка: {e}")
            
        print("✅ PostgreSQL подключена через внутренний URL")
        return True
    except Exception as e:
        print(f"❌ Ошибка через внутренний URL: {e}")
        
        # Пробуем через публичный URL
        try:
            print("🔌 Подключение через публичный URL...")
            pool = await asyncpg.create_pool(PUBLIC_DB_URL, min_size=1, max_size=5, timeout=15)
            
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
                
            print("✅ PostgreSQL подключена через публичный URL")
            return True
        except Exception as e2:
            print(f"❌ Ошибка через публичный URL: {e2}")
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
        print(f"✅ Создан игрок {username}")

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
