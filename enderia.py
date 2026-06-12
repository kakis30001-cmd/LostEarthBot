import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

from prompts import get_system_prompt, get_enderia_emojis, ENDERIA_EMOJI

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
# Активные игры
active_games = {}  # {chat_id: {"type": "guess_number", "target": number, "username": name}}
# Балансы игроков (алмазы)
player_balance = defaultdict(lambda: 100)  # У всех 100 алмазов старт
# Активные ставки
active_bets = {}  # {username: {"amount": int, "game": str}}

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

# ========== ПРОСТАЯ ЗАПИСЬ В ЛОГ ==========
LOG_FILE = "chat.log"

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
        print(f"📝 Лог: [{timestamp}] {who}: {message[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка лога: {e}")

def add_to_chat_memory(username: str, message: str, is_bot: bool = False):
    save_to_log(username, message, is_bot)

# ========== ПРЕМИУМ ЭМОДЗИ ==========
def get_random_emoji():
    emojis = list(ENDERIA_EMOJI.values())
    emoji_id = random.choice(emojis)
    return f'<tg-emoji emoji-id="{emoji_id}">💜</tg-emoji>'

def get_dice_emoji(value: int):
    dice_emojis = {
        1: "🎲 1",
        2: "🎲 2",
        3: "🎲 3",
        4: "🎲 4",
        5: "🎲 5",
        6: "🎲 6"
    }
    return dice_emojis.get(value, "🎲")

# ========== ИГРОВЫЕ ФУНКЦИИ ==========
def roll_dice() -> int:
    """Бросает кубик, возвращает число от 1 до 6"""
    return random.randint(1, 6)

async def game_guess_number_start(username: str, chat_id: int) -> str:
    """Начинает игру 'Угадай число'"""
    target = random.randint(1, 10)
    active_games[chat_id] = {
        "type": "guess_number",
        "target": target,
        "username": username,
        "attempts": 0
    }
    dice_emoji = get_random_emoji()
    return f"{dice_emoji} Загадала число от 1 до 10, {username}! Попробуй угадать! Пиши просто число 🎲\n{get_random_emoji()}"

async def game_guess_number_check(chat_id: int, guess: int, username: str) -> tuple[str, bool]:
    """Проверяет угадывание числа"""
    if chat_id not in active_games or active_games[chat_id]["type"] != "guess_number":
        return "", False
    
    game = active_games[chat_id]
    if username != game["username"]:
        return "", False
    
    game["attempts"] += 1
    target = game["target"]
    
    if guess == target:
        # Победа
        del active_games[chat_id]
        return f"{get_random_emoji()} {username}, ты угадал! 🎉 Это было число {target}! Потрачено попыток: {game['attempts']} {get_random_emoji()}", True
    elif guess < target:
        return f"{get_random_emoji()} {username}, загаданное число БОЛЬШЕ! Попробуй ещё 🐱", False
    else:
        return f"{get_random_emoji()} {username}, загаданное число МЕНЬШЕ! Попробуй ещё 🐱", False

async def game_dice_bet(username: str, bet_amount: int, chat_id: int) -> str:
    """Игра в кости на алмазы"""
    # Проверяем баланс
    if player_balance[username] < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {player_balance[username]} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    # Бросаем кубики
    player_dice = roll_dice()
    bot_dice = roll_dice()
    
    player_dice_emoji = get_dice_emoji(player_dice)
    bot_dice_emoji = get_dice_emoji(bot_dice)
    
    if player_dice > bot_dice:
        # Игрок выиграл
        win_amount = bet_amount * 2
        player_balance[username] += bet_amount
        result_text = f"🎉 ПОБЕДА! 🎉\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\nТы выиграл {bet_amount} алмазов! +{bet_amount} 💎"
        return f"{get_random_emoji()} {result_text}\n{get_random_emoji()}"
    elif player_dice < bot_dice:
        # Игрок проиграл
        player_balance[username] -= bet_amount
        result_text = f"😔 ПРОИГРЫШ... 😔\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\nТы проиграл {bet_amount} алмазов! -{bet_amount} 💎"
        return f"{get_random_emoji()} {result_text}\n{get_random_emoji()}"
    else:
        # Ничья
        result_text = f"🤝 НИЧЬЯ! 🤝\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\nСтавка возвращена! {bet_amount} 💎"
        return f"{get_random_emoji()} {result_text}\n{get_random_emoji()}"

async def game_dice_battle(username: str, chat_id: int) -> str:
    """Битва кубиков без ставки (просто игра)"""
    player_dice = roll_dice()
    bot_dice = roll_dice()
    
    player_dice_emoji = get_dice_emoji(player_dice)
    bot_dice_emoji = get_dice_emoji(bot_dice)
    
    if player_dice > bot_dice:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\n✨ Ты победил! ✨ {get_random_emoji()}"
    elif player_dice < bot_dice:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\n💔 Я победила! В следующий раз повезёт! 💔 {get_random_emoji()}"
    else:
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {player_dice_emoji}\nЭндерия: {bot_dice_emoji}\n\n🤝 Ничья! Боевая! 🤝 {get_random_emoji()}"

async def game_coinflip(username: str, bet_amount: int, choice: str, chat_id: int) -> str:
    """Орёл или решка на алмазы"""
    if player_balance[username] < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {player_balance[username]} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    # Монетка
    coin = random.choice(["орёл", "решка"])
    coin_emoji = "🦅" if coin == "орёл" else "🪙"
    
    if choice.lower() == coin:
        win_amount = bet_amount * 2
        player_balance[username] += bet_amount
        return f"{get_random_emoji()} 🪙 МОНЕТКА 🪙 {get_random_emoji()}\n\n{username}: {choice}\nЭндерия: {coin} {coin_emoji}\n\n✨ Ты угадал! +{bet_amount} алмазов! ✨\nБаланс: {player_balance[username]} 💎"
    else:
        player_balance[username] -= bet_amount
        return f"{get_random_emoji()} 🪙 МОНЕТКА 🪙 {get_random_emoji()}\n\n{username}: {choice}\nЭндерия: {coin} {coin_emoji}\n\n😔 Ты не угадал! -{bet_amount} алмазов! 😔\nБаланс: {player_balance[username]} 💎"

def get_balance(username: str) -> str:
    """Показывает баланс игрока"""
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
                    "max_tokens": 500,
                    "temperature": 0.85,
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data["choices"][0]["message"]["content"].strip()
                    return result, True
                else:
                    print(f"❌ Модель {model} ошибка {response.status}")
                    return "", False
    except asyncio.TimeoutError:
        print(f"⏰ Модель {model} таймаут")
        return "", False
    except Exception as e:
        print(f"⚠️ Модель {model} ошибка: {e}")
        return "", False

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False) -> str:
    global current_online, current_max
    
    print(f"🔍 Эндерия вызвана: {username} написал '{user_message}'")
    save_to_log(username, user_message, is_bot=False)
    
    msg_lower = user_message.lower()
    
    # ========== ОБРАБОТКА ИГР ==========
    
    # Команда /balance или /bal - показать баланс
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        response = get_balance(username)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Команда /dice - битва кубиков
    if user_message.startswith("/dice"):
        response = await game_dice_battle(username, message.chat.id)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Команда /bet [сумма] - ставка на кубик
    bet_match = re.match(r"^/bet\s+(\d+)$", user_message)
    if bet_match:
        bet_amount = int(bet_match.group(1))
        response = await game_dice_bet(username, bet_amount, message.chat.id)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Команда /coin [орёл/решка] [сумма]
    coin_match = re.match(r"^/coin\s+(орёл|решка)\s+(\d+)$", user_message.lower())
    if coin_match:
        choice = coin_match.group(1)
        bet_amount = int(coin_match.group(2))
        response = await game_coinflip(username, bet_amount, choice, message.chat.id)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Команда /guess - начать игру "Угадай число"
    if user_message.lower() == "/guess":
        response = await game_guess_number_start(username, message.chat.id)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Проверка угадывания числа
    if message.chat.id in active_games and active_games[message.chat.id]["type"] == "guess_number":
        try:
            guess = int(user_message.strip())
            response, ended = await game_guess_number_check(message.chat.id, guess, username)
            if response:
                add_to_memory(username, user_message, response)
                save_to_log(username, response, is_bot=True)
                return response
        except ValueError:
            pass
    
    # Команда /games - список игр
    if user_message.lower() == "/games":
        response = f"""{get_random_emoji()} <b>ДОСТУПНЫЕ ИГРЫ</b> {get_random_emoji()}

🎲 <b>/dice</b> - Битва кубиков с Эндерией
💰 <b>/bet 50</b> - Ставка на кубик (выигрыш х2)
🪙 <b>/coin орёл 50</b> - Орёл/Решка на алмазы
🎯 <b>/guess</b> - Угадай число от 1 до 10
💎 <b>/balance</b> - Показать баланс алмазов

<i>Стартовый баланс: 100 алмазов 💎</i>
{get_random_emoji()}"""
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    # Обычные разговоры с ИИ
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{get_random_emoji()} {username}, мы уже общаемся! Что хотел узнать про LostEarth? {get_random_emoji()}"
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    if not OPENROUTER_API_KEY:
        print("❌ НЕТ API КЛЮЧА! Использую fallback ответы.")
        fallbacks = [
            f"{get_random_emoji()} {username}, я Эндерия — хранительница Края! ✨ На LostEarth есть два режима: 🕊️ Мирный (PvP по согласию) и ⚔️ SMP (можно рейдить)! IP: 150.241.85.40:25565. Хочешь поиграть? Напиши /games! {get_random_emoji()}",
            f"{get_random_emoji()} {username}, привет! У нас есть игры: /dice (кубики), /bet (ставки), /coin (орёл/решка), /guess (угадай число). Проверим удачу? {get_random_emoji()}",
        ]
        response = random.choice(fallbacks)
        add_to_memory(username, user_message, response)
        save_to_log(username, response, is_bot=True)
        return response
    
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        system_prompt = get_system_prompt(username, current_time, current_online, current_max)
        
        full_prompt = f"""Игрок {username} написал: {user_message}

Ответь как Эндерия (4-6 предложений). Используй премиум эмодзи через теги <tg-emoji emoji-id="...">. Будь милой и дружелюбной.
Если спросят про игры - расскажи о /dice, /bet, /coin, /guess.
В конце поставь 1-2 премиум эмодзи."""
        
        for model in MODELS_CHAIN:
            try:
                print(f"🔄 Пробуем модель {model}")
                result, success = await ask_model(model, system_prompt, full_prompt)
                
                if success and result and len(result) > 10:
                    # Добавляем премиум эмодзи если их нет
                    if "<tg-emoji" not in result:
                        result += f" {get_random_emoji()}"
                    
                    if not already_greeted:
                        mark_greeted(username)
                    
                    add_to_memory(username, user_message, result)
                    save_to_log(username, result, is_bot=True)
                    return result
            except Exception as e:
                print(f"❌ Ошибка модели {model}: {e}")
                continue
            
            await asyncio.sleep(0.3)
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
    
    fallback = f"{get_random_emoji()} {username}, связь с Краем потеряна! Напиши /games чтобы поиграть, или повтори вопрос! {get_random_emoji()}"
    add_to_memory(username, user_message, fallback)
    save_to_log(username, fallback, is_bot=True)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
