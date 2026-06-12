import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
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

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
current_online = 0
current_max = 0

# ========== ИГРОВЫЕ ПЕРЕМЕННЫЕ ==========
active_games = {}
player_balance = defaultdict(lambda: 100)

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

# ========== ЗАПИСЬ В ЛОГ ==========
LOG_FILE = "chat.log"

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== ПРЕМИУМ ЭМОДЗИ (ПРОСТЫЕ ТЕКСТОВЫЕ) ==========
def get_random_emoji():
    emojis = ["💜", "🐱", "🐰", "✨", "🎲", "🪙", "💎", "🎯", "🕹️", "⭐"]
    return random.choice(emojis)

# ========== ИГРОВЫЕ ФУНКЦИИ ==========
def roll_dice():
    return random.randint(1, 6)

async def game_guess_number_start(username: str, chat_id: int) -> str:
    target = random.randint(1, 10)
    active_games[chat_id] = {
        "type": "guess_number",
        "target": target,
        "username": username,
        "attempts": 0
    }
    return f"{get_random_emoji()} Загадала число от 1 до 10, {username}! Попробуй угадать! Пиши просто число 🎲"

async def game_guess_number_check(chat_id: int, guess: int, username: str):
    if chat_id not in active_games or active_games[chat_id]["type"] != "guess_number":
        return "", False
    
    game = active_games[chat_id]
    if username != game["username"]:
        return "", False
    
    game["attempts"] += 1
    target = game["target"]
    
    if guess == target:
        del active_games[chat_id]
        return f"{get_random_emoji()} {username}, ты угадал! 🎉 Это было число {target}! Попыток: {game['attempts']} {get_random_emoji()}", True
    elif guess < target:
        return f"{get_random_emoji()} {username}, загаданное число БОЛЬШЕ! Попробуй ещё 🐱", False
    else:
        return f"{get_random_emoji()} {username}, загаданное число МЕНЬШЕ! Попробуй ещё 🐱", False

async def game_dice_bet(username: str, bet_amount: int) -> str:
    if player_balance[username] < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {player_balance[username]} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    player_dice = roll_dice()
    bot_dice = roll_dice()
    
    if player_dice > bot_dice:
        player_balance[username] += bet_amount
        return f"{get_random_emoji()} 🎲 ПОБЕДА! 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n✨ Ты выиграл {bet_amount} алмазов! +{bet_amount} 💎\nБаланс: {player_balance[username]} 💎"
    elif player_dice < bot_dice:
        player_balance[username] -= bet_amount
        return f"{get_random_emoji()} 🎲 ПРОИГРЫШ... 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n😔 Ты проиграл {bet_amount} алмазов! -{bet_amount} 💎\nБаланс: {player_balance[username]} 💎"
    else:
        return f"{get_random_emoji()} 🎲 НИЧЬЯ! 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n🤝 Ставка возвращена! {bet_amount} 💎\nБаланс: {player_balance[username]} 💎"

async def game_dice_battle(username: str) -> str:
    player_dice = roll_dice()
    bot_dice = roll_dice()
    
    if player_dice > bot_dice:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n✨ Ты победил! ✨"
    elif player_dice < bot_dice:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n💔 Я победила! В следующий раз повезёт! 💔"
    else:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲\n\n{username}: {player_dice}\nЭндерия: {bot_dice}\n\n🤝 Ничья! Боевая! 🤝"

async def game_coinflip(username: str, bet_amount: int, choice: str) -> str:
    if player_balance[username] < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {player_balance[username]} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    coin = random.choice(["орёл", "решка"])
    
    if choice.lower() == coin:
        player_balance[username] += bet_amount
        return f"{get_random_emoji()} 🪙 МОНЕТКА 🪙\n\n{username}: {choice}\nЭндерия: {coin}\n\n✨ Ты угадал! +{bet_amount} алмазов! ✨\nБаланс: {player_balance[username]} 💎"
    else:
        player_balance[username] -= bet_amount
        return f"{get_random_emoji()} 🪙 МОНЕТКА 🪙\n\n{username}: {choice}\nЭндерия: {coin}\n\n😔 Ты не угадал! -{bet_amount} алмазов! 😔\nБаланс: {player_balance[username]} 💎"

def get_balance(username: str) -> str:
    return f"{get_random_emoji()} {username}, твой баланс: {player_balance[username]} 💎 алмазов! {get_random_emoji()}"

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text_lower for g in greetings)

# ========== ЗАПРОС К МОДЕЛИ ==========
async def ask_model(model: str, system_prompt: str, user_prompt: str) -> tuple[str, bool]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.85,
                },
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data["choices"][0]["message"]["content"].strip()
                    return result, True
                else:
                    return "", False
    except:
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    
    # Обработка команд
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        response = get_balance(username)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    if user_message.startswith("/dice"):
        response = await game_dice_battle(username)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    bet_match = re.match(r"^/bet\s+(\d+)$", user_message)
    if bet_match:
        bet_amount = int(bet_match.group(1))
        response = await game_dice_bet(username, bet_amount)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    coin_match = re.match(r"^/coin\s+(орёл|решка)\s+(\d+)$", user_message.lower())
    if coin_match:
        choice = coin_match.group(1)
        bet_amount = int(coin_match.group(2))
        response = await game_coinflip(username, bet_amount, choice)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    if user_message.lower() == "/guess":
        if chat_id:
            response = await game_guess_number_start(username, chat_id)
        else:
            response = f"{get_random_emoji()} {username}, нажми /guess в чате, где хочешь играть!"
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    if chat_id and chat_id in active_games and active_games[chat_id]["type"] == "guess_number":
        try:
            guess = int(user_message.strip())
            response, ended = await game_guess_number_check(chat_id, guess, username)
            if response:
                add_to_memory(username, user_message, response)
                save_to_log(username, response, is_bot=True)
                return response
        except ValueError:
            pass
    
    if user_message.lower() == "/games":
        response = f"""{get_random_emoji()} ДОСТУПНЫЕ ИГРЫ {get_random_emoji()}

🎲 /dice - Битва кубиков с Эндерией
💰 /bet 50 - Ставка на кубик (выигрыш х2)
🪙 /coin орёл 50 - Орёл/Решка на алмазы
🎯 /guess - Угадай число от 1 до 10
💎 /balance - Показать баланс алмазов

Стартовый баланс: 100 алмазов 💎"""
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Обычный разговор
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{get_random_emoji()} {username}, мы уже общаемся! Что хотел узнать про LostEarth? Хочешь поиграть? Напиши /games"
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Если есть API ключ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            system_prompt = get_system_prompt(username, current_time, current_online, current_max)
            
            full_prompt = f"""Игрок {username} написал: {user_message}

Ответь как Эндерия (2-4 предложения). Будь милой и дружелюбной. Если спросят про игры - расскажи о /dice, /bet, /coin, /guess.
В конце поставь смайлик."""
            
            for model in MODELS_CHAIN:
                try:
                    result, success = await ask_model(model, system_prompt, full_prompt)
                    if success and result and len(result) > 10:
                        # Очищаем от возможных HTML тегов
                        result = re.sub(r'<[^>]+>', '', result)
                        if not already_greeted:
                            mark_greeted(username)
                        add_to_memory(username, user_message, result)
                        save_to_log(username, result, is_bot=True)
                        return result
                except:
                    continue
                await asyncio.sleep(0.3)
        except:
            pass
    
    # Fallback ответы
    fallbacks = [
        f"{get_random_emoji()} {username}, я Эндерия — хранительница Края! На LostEarth есть два режима: Мирный (PvP по согласию) и SMP (можно рейдить)! IP: 150.241.85.40:25565. Хочешь поиграть? Напиши /games",
        f"{get_random_emoji()} {username}, привет! У нас есть игры: /dice (кубики), /bet (ставки), /coin (орёл/решка), /guess (угадай число). Проверим удачу?",
        f"{get_random_emoji()} {username}, на LostEarth сейчас онлайн {current_online}/{current_max}. Заходи играть! А если хочешь поиграть со мной - напиши /games",
    ]
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
