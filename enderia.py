import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

# ========== ИМПОРТ БАЗЫ ДАННЫХ В САМОМ НАЧАЛЕ ==========
import asyncpg
from datetime import date

# Подключение к PostgreSQL на Railway
DATABASE_URL = os.getenv("DATABASE_URL")

# Если нет DATABASE_URL, собираем из отдельных переменных
if not DATABASE_URL:
    PGUSER = os.getenv("PGUSER")
    PGPASSWORD = os.getenv("PGPASSWORD")
    PGHOST = os.getenv("PGHOST")
    PGPORT = os.getenv("PGPORT", "5432")
    PGDATABASE = os.getenv("PGDATABASE")
    
    if PGUSER and PGPASSWORD and PGHOST and PGDATABASE:
        DATABASE_URL = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

# Кэш для быстрого доступа
balance_cache = {}
stats_cache = {}

# ========== ФУНКЦИИ БАЗЫ ДАННЫХ ==========
async def init_db():
    """Создаёт таблицы если их нет"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
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
    except:
        return balance_cache.get(username, 100)

async def create_player(username: str):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("INSERT INTO players (username, balance) VALUES ($1, 100)", username)
        await conn.close()
        balance_cache[username] = 100
    except:
        pass

async def update_balance(username: str, delta: int):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET balance = balance + $1, updated_at = NOW() WHERE username = $2", delta, username)
        await conn.close()
        if username in balance_cache:
            balance_cache[username] += delta
        else:
            balance_cache[username] = 100 + delta
    except:
        pass

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
        await conn.execute("UPDATE players SET balance = balance + 100, last_bonus = $1, updated_at = NOW() WHERE username = $2", date.today(), username)
        await conn.close()
        if username in balance_cache:
            balance_cache[username] += 100
        else:
            balance_cache[username] = 200
        return 100
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
    except:
        pass

async def get_stats(username: str) -> dict:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT wins, losses FROM players WHERE username = $1", username)
        await conn.close()
        if row:
            return {"wins": row[0], "losses": row[1]}
        return {"wins": 0, "losses": 0}
    except:
        return {"wins": 0, "losses": 0}

async def get_top_players(limit: int = 10) -> list:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("SELECT username, balance, wins, losses FROM players ORDER BY balance DESC LIMIT $1", limit)
        await conn.close()
        return [dict(row) for row in rows]
    except:
        return []

# ========== ОСТАЛЬНОЙ КОД ЭНДЕРИИ ==========
from prompts import get_system_prompt

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-oss-120b",
    "nousresearch/hermes-3-405b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "nvidia/nemotron-3-nano-30b-a3b",
]

current_online = 0
current_max = 0
active_games = {}

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

LOG_FILE = "chat.log"

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

def get_random_emoji():
    emojis = ["💜", "🐱", "🐰", "✨", "🎲", "🪙", "💎", "🎯", "⭐"]
    return random.choice(emojis)

# ========== ИГРЫ ==========
async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    balance = await get_balance(username)
    
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    await bot.send_message(chat_id, f"{get_random_emoji()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1)
    await bot.send_message(chat_id, f"{get_random_emoji()} Эндерия бросает кубик... 🎲")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        await update_balance(username, bet_amount)
        await update_stats(username, is_win=True)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} 🎲 ПОБЕДА! 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n✨ Ты выиграл {bet_amount} алмазов! +{bet_amount} 💎\nБаланс: {new_balance} 💎"
    elif player_value < bot_value:
        await update_balance(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} 🎲 ПРОИГРЫШ... 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n😔 Ты проиграл {bet_amount} алмазов! -{bet_amount} 💎\nБаланс: {new_balance} 💎"
    else:
        return f"{get_random_emoji()} 🎲 НИЧЬЯ! 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n🤝 Ставка возвращена!\nБаланс: {balance} 💎"

async def game_dice_battle(username: str, bot, chat_id: int) -> str:
    await bot.send_message(chat_id, f"{get_random_emoji()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1)
    await bot.send_message(chat_id, f"{get_random_emoji()} Эндерия бросает кубик... 🎲")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n✨ Ты победил! ✨"
    elif player_value < bot_value:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n💔 Я победила! В следующий раз повезёт! 💔"
    else:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_value}\nЭндерия: {bot_value}\n\n🤝 Ничья! 🤝"

async def game_coinflip(username: str, bet_amount: int, choice: str) -> str:
    balance = await get_balance(username)
    
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    coin = random.choice(["орёл", "решка"])
    coin_emoji = "🦅" if coin == "орёл" else "🪙"
    
    if choice.lower() == coin:
        await update_balance(username, bet_amount)
        await update_stats(username, is_win=True)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} 🪙 ПОБЕДА! 🪙\n\n{username}: {choice}\nЭндерия: {coin} {coin_emoji}\n\n✨ Ты выиграл {bet_amount} алмазов! +{bet_amount} 💎\nБаланс: {new_balance} 💎"
    else:
        await update_balance(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} 🪙 ПРОИГРЫШ... 🪙\n\n{username}: {choice}\nЭндерия: {coin} {coin_emoji}\n\n😔 Ты проиграл {bet_amount} алмазов! -{bet_amount} 💎\nБаланс: {new_balance} 💎"

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_greeted = {}
user_last_time = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()
    if username in user_greeted:
        user_greeted[username] = False

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def has_already_greeted(username: str) -> bool:
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    user_greeted[username] = True

def is_greeting(text: str) -> bool:
    text_lower = text.lower()
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик"]
    return any(g in text_lower for g in greetings)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    
    # Команды
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        balance = await get_balance(username)
        return f"{get_random_emoji()} {username}, твой баланс: {balance} 💎 алмазов!"
    
    if user_message.startswith("/dice"):
        if bot and chat_id:
            return await game_dice_battle(username, bot, chat_id)
        return f"{get_random_emoji()} {username}, эта игра работает только в чате с ботом! 🎲"
    
    bet_match = re.match(r"^/bet\s+(\d+)$", user_message)
    if bet_match and bot and chat_id:
        bet_amount = int(bet_match.group(1))
        return await game_dice_bet(username, bet_amount, bot, chat_id)
    
    coin_match = re.match(r"^/coin\s+(орёл|решка)\s+(\d+)$", user_message.lower())
    if coin_match:
        choice = coin_match.group(1)
        bet_amount = int(coin_match.group(2))
        return await game_coinflip(username, bet_amount, choice)
    
    if user_message.lower() == "/games":
        return f"""{get_random_emoji()} ДОСТУПНЫЕ ИГРЫ {get_random_emoji()}

🎲 /dice - Битва кубиков с Эндерией (бесплатно)
💰 /bet 50 - Ставка на кубик (выигрыш х2)
🪙 /coin орёл 50 - Орёл/Решка на алмазы
💎 /balance - Показать баланс
🎁 /daily - Ежедневный бонус 100💎
👤 /profile - Твой профиль
🏆 /top - Топ игроков

Стартовый баланс: 100 алмазов 💎"""
    
    if user_message.lower() == "/daily":
        if await can_claim_daily_bonus(username):
            bonus = await claim_daily_bonus(username)
            balance = await get_balance(username)
            return f"{get_random_emoji()} ЕЖЕДНЕВНЫЙ БОНУС! 🎁\n\n✨ +{bonus} 💎 алмазов!\n💎 Баланс: {balance} алмазов\n\nЗаходи завтра снова! {get_random_emoji()}"
        else:
            return f"{get_random_emoji()} {username}, ты уже получал бонус сегодня! Возвращайся завтра! 🎁"
    
    if user_message.lower() == "/profile":
        balance = await get_balance(username)
        stats = await get_stats(username)
        return f"{get_random_emoji()} ПРОФИЛЬ ИГРОКА 👤\n\nИмя: {username}\n💎 Баланс: {balance} алмазов\n🏆 Побед: {stats['wins']}\n💔 Поражений: {stats['losses']}\n📊 Всего игр: {stats['wins'] + stats['losses']}"
    
    if user_message.lower() == "/top":
        top = await get_top_players(10)
        if not top:
            return "📊 Топ игроков пока пуст! Будь первым! 🎲"
        text = f"{get_random_emoji()} ТОП ИГРОКОВ ПО АЛМАЗАМ 🏆\n\n"
        for i, p in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
            text += f"{medal} {p['username']} — {p['balance']} 💎 (🏆{p['wins']} | 💔{p['losses']})\n"
        return text
    
    # Обычный разговор
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    if already_greeted and is_greeting_msg and not is_reply:
        return f"{get_random_emoji()} {username}, мы уже общаемся! Что хотел узнать? Хочешь поиграть? Напиши /games"
    
    # Fallback
    fallbacks = [
        f"{get_random_emoji()} {username}, я Эндерия — хранительница Края! IP: 150.241.85.40:25565. Напиши /games чтобы поиграть! 🎲",
        f"{get_random_emoji()} {username}, привет! У нас есть игры: /dice, /bet, /coin. Проверим удачу?",
    ]
    return random.choice(fallbacks)

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
