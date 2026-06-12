import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

# ========== БАЗА ДАННЫХ ==========
import asyncpg
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    PGUSER = os.getenv("PGUSER")
    PGPASSWORD = os.getenv("PGPASSWORD")
    PGHOST = os.getenv("PGHOST")
    PGPORT = os.getenv("PGPORT", "5432")
    PGDATABASE = os.getenv("PGDATABASE")
    if PGUSER and PGPASSWORD and PGHOST and PGDATABASE:
        DATABASE_URL = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

balance_cache = {}

async def init_db():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                username TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 100,
                last_bonus DATE,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.close()
        print("✅ База данных готова")
        return True
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return False

async def get_balance(username: str) -> int:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT balance FROM players WHERE username = $1", username)
        await conn.close()
        if row:
            return row[0]
        else:
            await conn.execute("INSERT INTO players (username, balance) VALUES ($1, 100)", username)
            return 100
    except:
        return 100

async def update_balance(username: str, delta: int):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE players SET balance = balance + $1 WHERE username = $2", delta, username)
        await conn.close()
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
        await conn.execute("UPDATE players SET balance = balance + 100, last_bonus = $1 WHERE username = $2", date.today(), username)
        await conn.close()
        return 100
    except:
        return 0

async def update_stats(username: str, is_win: bool):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        if is_win:
            await conn.execute("UPDATE players SET wins = wins + 1 WHERE username = $1", username)
        else:
            await conn.execute("UPDATE players SET losses = losses + 1 WHERE username = $1", username)
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

# ========== ОСТАЛЬНОЙ КОД ==========
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
    emojis = ["💜", "🐱", "🐰", "✨", "🎲", "💎", "🎯", "⭐"]
    return random.choice(emojis)

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=10))
user_greeted = {}

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username]))

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text_lower for g in greetings)

# ========== ИГРЫ ==========
async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    balance = await get_balance(username)
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1)
    await bot.send_message(chat_id, f"🎲 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        await update_balance(username, bet_amount)
        await update_stats(username, is_win=True)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} ПОБЕДА! 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance}"
    elif player_value < bot_value:
        await update_balance(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} ПРОИГРЫШ... 😔\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n😭 Ты проиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance}"
    else:
        return f"{get_random_emoji()} НИЧЬЯ! 🤝\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💎 Баланс: {balance}"

async def game_dice_battle(username: str, bot, chat_id: int) -> str:
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1)
    await bot.send_message(chat_id, f"🎲 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        return f"{get_random_emoji()} ТЫ ПОБЕДИЛ! 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Отличная игра!"
    elif player_value < bot_value:
        return f"{get_random_emoji()} Я ПОБЕДИЛА! 😊\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💪 В следующий раз повезёт!"
    else:
        return f"{get_random_emoji()} НИЧЬЯ! 🤝\n\nОба выбросили {player_value}\n\n🎲 Сыграем ещё?"

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
        return f"{get_random_emoji()} ПОБЕДА! 🎉\n\nТвой выбор: {choice}\nВыпало: {coin} {coin_emoji}\n\n✨ Ты выиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance}"
    else:
        await update_balance(username, -bet_amount)
        await update_stats(username, is_win=False)
        new_balance = await get_balance(username)
        return f"{get_random_emoji()} ПРОИГРЫШ... 😔\n\nТвой выбор: {choice}\nВыпало: {coin} {coin_emoji}\n\n😭 Ты проиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance}"

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    
    # ========== ИГРОВЫЕ КОМАНДЫ ==========
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        balance = await get_balance(username)
        response = f"{get_random_emoji()} {username}, твой баланс: {balance} 💎 алмазов!"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/daily"):
        if await can_claim_daily_bonus(username):
            bonus = await claim_daily_bonus(username)
            balance = await get_balance(username)
            response = f"{get_random_emoji()} ЕЖЕДНЕВНЫЙ БОНУС! 🎁\n\n✨ +{bonus} 💎 алмазов!\n💎 Баланс: {balance} алмазов\n\nЗаходи завтра снова!"
        else:
            response = f"{get_random_emoji()} {username}, ты уже получал бонус сегодня! Возвращайся завтра!"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/profile"):
        balance = await get_balance(username)
        stats = await get_stats(username)
        response = f"{get_random_emoji()} ПРОФИЛЬ ИГРОКА 👤\n\nИмя: {username}\n💎 Баланс: {balance} алмазов\n🏆 Побед: {stats['wins']}\n💔 Поражений: {stats['losses']}"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/top"):
        top = await get_top_players(10)
        if not top:
            response = "📊 Топ игроков пока пуст! Будь первым!"
        else:
            text = f"{get_random_emoji()} ТОП ИГРОКОВ ПО АЛМАЗАМ 🏆\n\n"
            for i, p in enumerate(top, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
                text += f"{medal} {p['username']} — {p['balance']} 💎\n"
            response = text
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/dice"):
        if bot and chat_id:
            response = await game_dice_battle(username, bot, chat_id)
        else:
            response = f"{get_random_emoji()} {username}, напиши /dice в чате со мной!"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/bet"):
        match = re.match(r"^/bet\s+(\d+)$", user_message)
        if match and bot and chat_id:
            bet_amount = int(match.group(1))
            response = await game_dice_bet(username, bet_amount, bot, chat_id)
        else:
            response = f"{get_random_emoji()} {username}, используй: /bet [сумма] (например /bet 50)"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/coin"):
        match = re.match(r"^/coin\s+(орёл|решка)\s+(\d+)$", user_message.lower())
        if match:
            choice = match.group(1)
            bet_amount = int(match.group(2))
            response = await game_coinflip(username, bet_amount, choice)
        else:
            response = f"{get_random_emoji()} {username}, используй: /coin орёл 50 или /coin решка 100"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/games"):
        response = f"""{get_random_emoji()} <b>ДОСТУПНЫЕ ИГРЫ</b> {get_random_emoji()}

🎲 /dice - Битва кубиков (бесплатно)
💰 /bet 50 - Ставка на кубик (выигрыш х2)
🪙 /coin орёл 50 - Орёл/Решка
💎 /balance - Показать баланс
🎁 /daily - Бонус 100💎 каждый день
👤 /profile - Твой профиль
🏆 /top - Топ игроков

<i>Стартовый баланс: 100 алмазов 💎</i>"""
        add_to_memory(username, user_message, response)
        return response
    
    # ========== ОБЫЧНЫЙ РАЗГОВОР ==========
    history = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{get_random_emoji()} {username}, мы уже общаемся! Что хотел узнать? Напиши /games чтобы поиграть!"
        add_to_memory(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        system_prompt = get_system_prompt(username, current_time, current_online, current_max)
        
        full_prompt = f"""Вот история нашего диалога с {username}:
{history if history else "Пока пусто"}

Сейчас {username} написал: {user_message}

Ответь как Эндерия, учитывая историю разговора. Если вы уже общались - НЕ ЗДОРОВАЙСЯ заново.
Будь милой и дружелюбной. Если спросят про игры - расскажи о /games.
Ответь 3-5 предложениями, закончи мысль. В конце эмодзи."""
        
        for model in MODELS_CHAIN:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": full_prompt}
                            ],
                            "max_tokens": 400,
                            "temperature": 0.85,
                        },
                        timeout=aiohttp.ClientTimeout(total=25)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = data["choices"][0]["message"]["content"].strip()
                            result = re.sub(r'<[^>]+>', '', result)
                            
                            # Проверяем, не обрезано ли сообщение
                            if len(result) < 50 and "..." in result:
                                # Если обрезано - добавляем ещё
                                result += " 🌸💜"
                            
                            if not already_greeted:
                                mark_greeted(username)
                            
                            add_to_memory(username, user_message, result)
                            return result
            except:
                continue
    except:
        pass
    
    # Fallback
    fallback = f"{get_random_emoji()} {username}, я Эндерия — хранительница Края! Хочешь поиграть? Напиши /games 🎲"
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
