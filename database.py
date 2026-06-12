import os
import asyncpg
from datetime import date
from typing import Optional, Dict, Any

DATABASE_URL = os.getenv("DATABASE_URL")

# Кэш для быстрого доступа
balance_cache = {}
stats_cache = {}

async def init_db():
    """Создаёт таблицы если их нет"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Таблица игроков
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                username TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 100,
                last_bonus DATE,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        await conn.close()
        print("✅ PostgreSQL база данных инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

async def get_balance(username: str) -> int:
    """Получает баланс игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT balance FROM players WHERE username = $1", username)
        await conn.close()
        
        if row:
            balance_cache[username] = row[0]
            return row[0]
        else:
            await create_player(username)
            return 100
    except Exception as e:
        print(f"❌ Ошибка получения баланса: {e}")
        return balance_cache.get(username, 100)

async def create_player(username: str):
    """Создаёт нового игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO players (username, balance)
            VALUES ($1, 100)
        """, username)
        await conn.close()
        balance_cache[username] = 100
        print(f"✅ Создан игрок {username}")
    except Exception as e:
        print(f"❌ Ошибка создания игрока: {e}")

async def update_balance(username: str, delta: int):
    """Обновляет баланс игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE players 
            SET balance = balance + $1, updated_at = NOW()
            WHERE username = $2
        """, delta, username)
        await conn.close()
        
        if username in balance_cache:
            balance_cache[username] += delta
        else:
            balance_cache[username] = 100 + delta
    except Exception as e:
        print(f"❌ Ошибка обновления баланса: {e}")

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
    """Начисляет ежедневный бонус 100 алмазов"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE players 
            SET balance = balance + 100, last_bonus = $1, updated_at = NOW()
            WHERE username = $2
        """, date.today(), username)
        await conn.close()
        
        if username in balance_cache:
            balance_cache[username] += 100
        else:
            balance_cache[username] = 200
        return 100
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
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT wins, losses FROM players WHERE username = $1", username)
        await conn.close()
        
        if row:
            return {"wins": row[0], "losses": row[1]}
        return {"wins": 0, "losses": 0}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {"wins": 0, "losses": 0}

async def get_top_players(limit: int = 10) -> list:
    """Получает топ игроков по балансу"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT username, balance, wins, losses 
            FROM players 
            ORDER BY balance DESC 
            LIMIT $1
        """, limit)
        await conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Ошибка получения топа: {e}")
        return []
