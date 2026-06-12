import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime, date
from collections import defaultdict, deque
from dotenv import load_dotenv

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

# ========== ПРОСТОЕ ФАЙЛОВОЕ ХРАНИЛИЩЕ (БЕЗ БД) ==========
PLAYERS_FILE = "players.json"

def load_players():
    if not os.path.exists(PLAYERS_FILE):
        return {}
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_players(data):
    try:
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_balance(username: str) -> int:
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        save_players(data)
    return data[username].get("balance", 100)

def update_balance(username: str, delta: int):
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["balance"] = data[username].get("balance", 100) + delta
    save_players(data)

def can_claim_daily_bonus(username: str) -> bool:
    data = load_players()
    if username not in data:
        return True
    last_bonus = data[username].get("last_bonus")
    if not last_bonus:
        return True
    return last_bonus != str(date.today())

def claim_daily_bonus(username: str) -> int:
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["balance"] = data[username].get("balance", 100) + 100
    data[username]["last_bonus"] = str(date.today())
    save_players(data)
    return 100

def update_stats(username: str, is_win: bool):
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    if is_win:
        data[username]["wins"] = data[username].get("wins", 0) + 1
    else:
        data[username]["losses"] = data[username].get("losses", 0) + 1
    save_players(data)

def get_stats(username: str) -> dict:
    data = load_players()
    if username not in data:
        return {"wins": 0, "losses": 0}
    return {"wins": data[username].get("wins", 0), "losses": data[username].get("losses", 0)}

def get_top_players(limit: int = 10) -> list:
    data = load_players()
    players = []
    for name, info in data.items():
        players.append({
            "username": name,
            "balance": info.get("balance", 100),
            "wins": info.get("wins", 0)
        })
    players.sort(key=lambda x: x["balance"], reverse=True)
    return players[:limit]

# ========== ОСТАЛЬНОЙ КОД ==========
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
    emojis = ["💜", "🐱", "🐰", "✨", "🎲", "💎", "🎯", "⭐", "🌸", "🪙", "🎉", "😊", "🥳"]
    return random.choice(emojis)

# ========== ПАМЯТЬ ДИАЛОГОВ ==========
user_memory = defaultdict(lambda: deque(maxlen=20))
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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "доброе утро", "добрый день"]
    return any(g in text_lower for g in greetings)

# ========== ИГРЫ ==========
async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    balance = get_balance(username)
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    await bot.send_message(chat_id, f"{get_random_emoji()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"{get_random_emoji()} Эндерия бросает кубик... 🎲")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        update_balance(username, bet_amount)
        update_stats(username, is_win=True)
        new_balance = get_balance(username)
        return f"{get_random_emoji()} 🎉 ПОБЕДА! 🎉 {get_random_emoji()}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_random_emoji()}"
    elif player_value < bot_value:
        update_balance(username, -bet_amount)
        update_stats(username, is_win=False)
        new_balance = get_balance(username)
        return f"{get_random_emoji()} 😔 ПРОИГРЫШ... 😔 {get_random_emoji()}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_random_emoji()}"
    else:
        return f"{get_random_emoji()} 🤝 НИЧЬЯ! 🤝 {get_random_emoji()}\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💎 Баланс: {balance} {get_random_emoji()}"

async def game_dice_battle(username: str, bot, chat_id: int) -> str:
    await bot.send_message(chat_id, f"{get_random_emoji()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"{get_random_emoji()} Эндерия бросает кубик... 🎲")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        return f"{get_random_emoji()} 🏆 ТЫ ПОБЕДИЛ! 🏆 {get_random_emoji()}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Отличная игра! ✨"
    elif player_value < bot_value:
        return f"{get_random_emoji()} 👑 Я ПОБЕДИЛА! 👑 {get_random_emoji()}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💫 В следующий раз повезёт! 💫"
    else:
        return f"{get_random_emoji()} 🤝 НИЧЬЯ! 🤝 {get_random_emoji()}\n\nОба выбросили {player_value}\n\n🎲 Сыграем ещё? Напиши /dice {get_random_emoji()}"

async def game_coinflip(username: str, bet_amount: int, choice: str) -> str:
    balance = get_balance(username)
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    coin = random.choice(["орёл", "решка"])
    coin_emoji = "🦅" if coin == "орёл" else "🪙"
    
    if choice.lower() == coin:
        update_balance(username, bet_amount)
        update_stats(username, is_win=True)
        new_balance = get_balance(username)
        return f"{get_random_emoji()} 🎉 ПОБЕДА! 🎉 {get_random_emoji()}\n\nТвой выбор: {choice}\nВыпало: {coin} {coin_emoji}\n\n✨ Ты выиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_random_emoji()}"
    else:
        update_balance(username, -bet_amount)
        update_stats(username, is_win=False)
        new_balance = get_balance(username)
        return f"{get_random_emoji()} 😔 ПРОИГРЫШ... 😔 {get_random_emoji()}\n\nТвой выбор: {choice}\nВыпало: {coin} {coin_emoji}\n\n💔 Ты проиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_random_emoji()}"

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    
    # ========== ИГРОВЫЕ КОМАНДЫ ==========
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        balance = get_balance(username)
        response = f"{get_random_emoji()} {username}, твой баланс: {balance} 💎 алмазов! {get_random_emoji()}"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/daily"):
        if can_claim_daily_bonus(username):
            bonus = claim_daily_bonus(username)
            balance = get_balance(username)
            response = f"{get_random_emoji()} 🎁 ЕЖЕДНЕВНЫЙ БОНУС! 🎁 {get_random_emoji()}\n\n✨ +{bonus} 💎 алмазов!\n💎 Баланс: {balance} алмазов\n\n🌸 Заходи завтра снова! 🌸"
        else:
            response = f"{get_random_emoji()} {username}, ты уже получал бонус сегодня! Возвращайся завтра! 🌸"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/profile"):
        balance = get_balance(username)
        stats = get_stats(username)
        response = f"{get_random_emoji()} 👤 ПРОФИЛЬ ИГРОКА 👤 {get_random_emoji()}\n\n👤 Имя: {username}\n💎 Баланс: {balance} алмазов\n🏆 Побед: {stats['wins']}\n💔 Поражений: {stats['losses']}\n📊 Всего игр: {stats['wins'] + stats['losses']}\n\n{get_random_emoji()} Напиши /games чтобы играть! {get_random_emoji()}"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/top"):
        top = get_top_players(10)
        if not top:
            response = f"{get_random_emoji()} 📊 Топ игроков пока пуст! Будь первым! 🎲 {get_random_emoji()}"
        else:
            text = f"{get_random_emoji()} 🏆 ТОП ИГРОКОВ ПО АЛМАЗАМ 🏆 {get_random_emoji()}\n\n"
            for i, p in enumerate(top, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
                text += f"{medal} {p['username']} — {p['balance']} 💎 (🏆{p['wins']})\n"
            response = text
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/dice"):
        if bot and chat_id:
            response = await game_dice_battle(username, bot, chat_id)
        else:
            response = f"{get_random_emoji()} {username}, напиши /dice в чате со мной! 🎲"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/bet"):
        match = re.match(r"^/bet\s+(\d+)$", user_message)
        if match and bot and chat_id:
            bet_amount = int(match.group(1))
            if bet_amount < 10:
                response = f"{get_random_emoji()} {username}, минимальная ставка 10 алмазов! 💎"
            else:
                response = await game_dice_bet(username, bet_amount, bot, chat_id)
        else:
            response = f"{get_random_emoji()} {username}, используй: /bet [сумма] (например /bet 50) 🎲"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/coin"):
        match = re.match(r"^/coin\s+(орёл|решка)\s+(\d+)$", user_message.lower())
        if match:
            choice = match.group(1)
            bet_amount = int(match.group(2))
            if bet_amount < 10:
                response = f"{get_random_emoji()} {username}, минимальная ставка 10 алмазов! 💎"
            else:
                response = await game_coinflip(username, bet_amount, choice)
        else:
            response = f"{get_random_emoji()} {username}, используй: /coin орёл 50 или /coin решка 100 🪙"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/games"):
        response = f"""{get_random_emoji()} 🎮 <b>ДОСТУПНЫЕ ИГРЫ</b> 🎮 {get_random_emoji()}

🎲 /dice - Битва кубиков (бесплатно)
💰 /bet [сумма] - Ставка на кубик (выигрыш х2)
🪙 /coin [орёл/решка] [сумма] - Орёл/Решка на алмазы
💎 /balance - Показать баланс
🎁 /daily - Бонус 100💎 каждый день
👤 /profile - Твой профиль
🏆 /top - Топ игроков

✨ Стартовый баланс: 100 алмазов 💎
🌸 Минимальная ставка: 10 алмазов

{get_random_emoji()} Удачи в играх! {get_random_emoji()}"""
        add_to_memory(username, user_message, response)
        return response
    
    # ========== ОБЫЧНЫЙ РАЗГОВОР С ПАМЯТЬЮ ==========
    history = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{get_random_emoji()} {username}, мы уже общаемся! Что хотел узнать про LostEarth? Хочешь поиграть? Напиши /games {get_random_emoji()}"
        add_to_memory(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            system_prompt = get_system_prompt(username, current_time, current_online, current_max)
            
            full_prompt = f"""Вот история нашего диалога с {username}:
{history if history else "Пока пусто"}

Сейчас {username} написал: {user_message}

Ответь как Эндерия, учитывая историю разговора.
ВАЖНО: Если вы уже общались - НЕ ЗДОРОВАЙСЯ заново!
Будь милой, дружелюбной, используй эмодзи. Отвечай 3-5 предложениями.
Обязательно закончи мысль и поставь эмодзи в конце."""
            
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
                                "max_tokens": 600,
                                "temperature": 0.9,
                            },
                            timeout=aiohttp.ClientTimeout(total=40)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                
                                if not already_greeted:
                                    mark_greeted(username)
                                
                                add_to_memory(username, user_message, result)
                                return result
                except:
                    continue
        except:
            pass
    
    # Fallback ответы
    fallbacks = [
        f"{get_random_emoji()} {username}, я Эндерия — хранительница Края! ✨\n\nIP Java: 150.241.85.40:25565\nХочешь поиграть? Напиши /games 🎲 {get_random_emoji()}",
        f"{get_random_emoji()} {username}, привет! У нас есть игры: /dice, /bet, /coin. Проверим удачу? 🎲 {get_random_emoji()}",
        f"{get_random_emoji()} {username}, на LostEarth есть два режима: Мирный и SMP. IP: 150.241.85.40:25565\n\nНапиши /games чтобы поиграть! 🎮 {get_random_emoji()}",
    ]
    response = random.choice(fallbacks)
    
    if not already_greeted:
        mark_greeted(username)
    
    add_to_memory(username, user_message, response)
    return response

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
