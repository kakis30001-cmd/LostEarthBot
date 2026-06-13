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
        print("📌 Добавь PostgreSQL плагин в Railway!")
        return False
    
    try:
        print(f"🔌 Подключение к БД...")
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        
        async with pool.acquire() as conn:
            # Таблица игроков
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
            
            # Таблица истории сообщений
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                is_bot BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            # Таблица диалогов Энди
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS andy_dialogs(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                user_message TEXT,
                andy_response TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            # Таблица для статистики чата
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_stats(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                messages_count INTEGER DEFAULT 0,
                last_message TIMESTAMP,
                UNIQUE(username)
            )
            """)
            
            # Индексы для быстрого поиска
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_username ON chat_history(username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_andy_dialogs_username ON andy_dialogs(username)")
            
        print("✅ PostgreSQL подключена! Все таблицы созданы")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

async def init_db():
    return await connect_db()

# Добавьте эту функцию в database.py

async def check_user_subscribed(username: str, bot, channel_username: str) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        # Получаем ID пользователя по username
        # Нам нужно где-то хранить mapping username -> user_id
        # Временно сделаем через таблицу
        async with pool.acquire() as conn:
            # Пытаемся получить user_id из таблицы
            row = await conn.fetchrow("SELECT user_id FROM players WHERE username = $1", username)
            if not row or not row["user_id"]:
                return False
            
            user_id = row["user_id"]
            member = await bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
            return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

async def save_user_id(username: str, user_id: int):
    """Сохраняет связь username -> user_id"""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE players SET user_id = $1 
            WHERE username = $2 AND (user_id IS NULL OR user_id != $1)
        """, user_id, username)

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

# ========== ФУНКЦИИ ФАРМЫ ==========
async def get_farm_level(username: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT farm_level FROM players WHERE username = $1", username)
        return row["farm_level"] if row else 1

async def update_farm_level(username: str, new_level: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET farm_level = $1, updated_at = NOW() WHERE username = $2", new_level, username)

async def get_last_farm(username: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_farm FROM players WHERE username = $1", username)
        return row["last_farm"] if row else None

async def update_last_farm(username: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE players SET last_farm = NOW() WHERE username = $1", username)

# ========== ФУНКЦИИ ИСТОРИИ ЧАТА ==========
async def save_chat_message(username: str, message: str, is_bot: bool = False):
    """Сохраняет сообщение в историю чата"""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_history (username, message, is_bot) VALUES ($1, $2, $3)",
            username, message, is_bot
        )
        
        # Обновляем статистику
        await conn.execute("""
            INSERT INTO chat_stats (username, messages_count, last_message) 
            VALUES ($1, 1, NOW())
            ON CONFLICT (username) DO UPDATE SET 
                messages_count = chat_stats.messages_count + 1,
                last_message = NOW()
        """, username)

async def save_andy_dialog(username: str, user_message: str, andy_response: str):
    """Сохраняет диалог с Энди"""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO andy_dialogs (username, user_message, andy_response) VALUES ($1, $2, $3)",
            username, user_message, andy_response
        )

async def get_chat_history(limit: int = 50, username: str = None) -> list:
    """Получает историю чата (последние сообщения)"""
    async with pool.acquire() as conn:
        if username:
            rows = await conn.fetch("""
                SELECT username, message, is_bot, created_at 
                FROM chat_history 
                WHERE username = $1
                ORDER BY created_at DESC 
                LIMIT $2
            """, username, limit)
        else:
            rows = await conn.fetch("""
                SELECT username, message, is_bot, created_at 
                FROM chat_history 
                ORDER BY created_at DESC 
                LIMIT $1
            """, limit)
        return [dict(row) for row in rows]

async def get_andy_dialogs(username: str = None, limit: int = 20) -> list:
    """Получает историю диалогов с Энди"""
    async with pool.acquire() as conn:
        if username:
            rows = await conn.fetch("""
                SELECT user_message, andy_response, created_at 
                FROM andy_dialogs 
                WHERE username = $1
                ORDER BY created_at DESC 
                LIMIT $2
            """, username, limit)
        else:
            rows = await conn.fetch("""
                SELECT username, user_message, andy_response, created_at 
                FROM andy_dialogs 
                ORDER BY created_at DESC 
                LIMIT $1
            """, limit)
        return [dict(row) for row in rows]

async def get_chat_stats(username: str = None) -> dict:
    """Получает статистику чата"""
    async with pool.acquire() as conn:
        if username:
            row = await conn.fetchrow("""
                SELECT messages_count, last_message 
                FROM chat_stats 
                WHERE username = $1
            """, username)
            return dict(row) if row else {"messages_count": 0, "last_message": None}
        else:
            # Общая статистика
            total_messages = await conn.fetchval("SELECT COUNT(*) FROM chat_history WHERE is_bot = FALSE")
            total_bot_messages = await conn.fetchval("SELECT COUNT(*) FROM chat_history WHERE is_bot = TRUE")
            unique_users = await conn.fetchval("SELECT COUNT(DISTINCT username) FROM chat_history")
            return {
                "total_messages": total_messages,
                "total_bot_messages": total_bot_messages,
                "unique_users": unique_users
            }

async def clear_old_history(days: int = 30):
    """Очищает старую историю (старше указанного количества дней)"""
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM chat_history 
            WHERE created_at < NOW() - INTERVAL '$1 days'
        """, days)
        await conn.execute("""
            DELETE FROM andy_dialogs 
            WHERE created_at < NOW() - INTERVAL '$1 days'
        """, days)

# ========== ТОП ИГРОКОВ ==========
async def get_leaderboard(limit: int = 10) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT username, xp, wins, losses, farm_level
            FROM players
            ORDER BY xp DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
