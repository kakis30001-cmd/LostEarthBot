import os
import asyncpg
from datetime import datetime, date
from collections import defaultdict

DATABASE_URL = os.getenv("DATABASE_URL")

# Кэш для быстрого доступа (на случай ошибок БД)
balance_cache = defaultdict(lambda: 100)
last_bonus_cache = {}

async def init_db():
    """Создаёт таблицы если их нет"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS player_balance (
                username TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 100,
                last_bonus DATE,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.close()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

async def get_balance(username: str) -> int:
    """Получает баланс игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT balance FROM player_balance WHERE username = $1", username)
        await conn.close()
        
        if row:
            balance_cache[username] = row[0]
            return row[0]
        else:
            # Создаём нового игрока
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
            INSERT INTO player_balance (username, balance, last_bonus)
            VALUES ($1, 100, NULL)
        """, username)
        await conn.close()
        balance_cache[username] = 100
        print(f"✅ Создан игрок {username}")
    except Exception as e:
        print(f"❌ Ошибка создания игрока: {e}")

async def update_balance(username: str, delta: int):
    """Обновляет баланс игрока (+ или -)"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE player_balance 
            SET balance = balance + $1, updated_at = NOW()
            WHERE username = $2
        """, delta, username)
        await conn.close()
        
        # Обновляем кэш
        if username in balance_cache:
            balance_cache[username] += delta
        else:
            balance_cache[username] = 100 + delta
    except Exception as e:
        print(f"❌ Ошибка обновления баланса: {e}")
        balance_cache[username] = balance_cache.get(username, 100) + delta

async def can_claim_daily_bonus(username: str) -> bool:
    """Проверяет, можно ли получить ежедневный бонус"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT last_bonus FROM player_balance WHERE username = $1", username)
        await conn.close()
        
        if not row or row[0] is None:
            return True
        
        last_bonus = row[0]
        return last_bonus < date.today()
    except Exception as e:
        print(f"❌ Ошибка проверки бонуса: {e}")
        return last_bonus_cache.get(username, date(1970,1,1)) < date.today()

async def claim_daily_bonus(username: str) -> int:
    """Начисляет ежедневный бонус 100 алмазов"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            UPDATE player_balance 
            SET balance = balance + 100, last_bonus = $1, updated_at = NOW()
            WHERE username = $2
        """, date.today(), username)
        await conn.close()
        
        balance_cache[username] = balance_cache.get(username, 100) + 100
        last_bonus_cache[username] = date.today()
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
                UPDATE player_balance 
                SET total_wins = total_wins + 1, updated_at = NOW()
                WHERE username = $1
            """, username)
        else:
            await conn.execute("""
                UPDATE player_balance 
                SET total_losses = total_losses + 1, updated_at = NOW()
                WHERE username = $1
            """, username)
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления статистики: {e}")

async def get_stats(username: str) -> dict:
    """Получает статистику игрока"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT total_wins, total_losses FROM player_balance WHERE username = $1", username)
        await conn.close()
        
        if row:
            return {"wins": row[0], "losses": row[1]}
        return {"wins": 0, "losses": 0}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {"wins": 0, "losses": 0}
