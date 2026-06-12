import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime, date
from collections import defaultdict, deque
from dotenv import load_dotenv

from prompts import get_system_prompt, get_enderia_emojis, emoji, ENDERIA_EMOJI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-oss-120b",
    "nousresearch/hermes-3-405b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "nvidia/nemotron-3-nano-30b-a3b",
]

# ========== ФАЙЛОВОЕ ХРАНИЛИЩЕ ==========
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

def can_claim_daily_bonus(username: str) -> bool:
    data = load_players()
    if username not in data:
        return True
    last_bonus = data[username].get("last_bonus")
    if not last_bonus:
        return True
    return last_bonus != str(date.today())

def set_daily_bonus_claimed(username: str):
    data = load_players()
    if username not in data:
        data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
    data[username]["last_bonus"] = str(date.today())
    save_players(data)

def check_and_add_bonus(username: str, has_description: bool) -> tuple[bool, int]:
    if not has_description:
        return False, 0
    
    if can_claim_daily_bonus(username):
        data = load_players()
        if username not in data:
            data[username] = {"balance": 100, "last_bonus": None, "wins": 0, "losses": 0}
        data[username]["balance"] = data[username].get("balance", 100) + 100
        data[username]["last_bonus"] = str(date.today())
        save_players(data)
        return True, 100
    return False, 0

# ========== ОСТАЛЬНОЙ КОД ==========
current_online = 0
current_max = 0

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text_lower for g in greetings)

def is_just_name(text: str) -> bool:
    """Проверяет, зовут ли просто по имени"""
    text_lower = text.lower().strip()
    names = ["энди", "эндер", "эндерия", "ендер", "енди"]
    # Если сообщение состоит только из имени или имени с восклицательным знаком
    clean_text = re.sub(r'[!?.]', '', text_lower).strip()
    return clean_text in names

# ========== ИГРЫ ==========
async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    balance = get_balance(username)
    if balance < bet_amount:
        return f"{get_enderia_emojis()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount < 10:
        return f"{get_enderia_emojis()} {username}, минимальная ставка 10 алмазов! 💎"
    
    await bot.send_message(chat_id, f"{get_enderia_emojis()} {username} бросает кубик... 🎲")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"{get_enderia_emojis()} Я бросаю кубик... 🎲")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        update_balance(username, bet_amount)
        update_stats(username, is_win=True)
        new_balance = get_balance(username)
        return f"{emoji(ENDERIA_EMOJI['cat_dance'], '🎉')} ПОБЕДА! {emoji(ENDERIA_EMOJI['cat_dance'], '🎉')}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_enderia_emojis(1)}"
    elif player_value < bot_value:
        update_balance(username, -bet_amount)
        update_stats(username, is_win=False)
        new_balance = get_balance(username)
        return f"{emoji(ENDERIA_EMOJI['cat_surprised'], '😔')} ПРОИГРЫШ... {emoji(ENDERIA_EMOJI['cat_surprised'], '😔')}\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} алмазов!\n💎 Баланс: {new_balance} {get_enderia_emojis(1)}"
    else:
        return f"{emoji(ENDERIA_EMOJI['heart'], '🤝')} НИЧЬЯ! {emoji(ENDERIA_EMOJI['heart'], '🤝')}\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💎 Баланс: {balance} {get_enderia_emojis(1)}"

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None, user_bio: str = "") -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    
    # Проверка на наличие @lostearth_bot в описании
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    # ========== КОМАНДЫ ==========
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        balance = get_balance(username)
        response = f"{get_enderia_emojis()} {username}, твой баланс: {balance} 💎 алмазов! {get_enderia_emojis(1)}"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/profile"):
        balance = get_balance(username)
        stats = get_stats(username)
        response = f"""{emoji(ENDERIA_EMOJI['crown'], '👤')} <b>ПРОФИЛЬ ИГРОКА</b> {emoji(ENDERIA_EMOJI['crown'], '👤')}

👤 Имя: {username}
💎 Баланс: {balance} алмазов
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
📊 Всего игр: {stats['wins'] + stats['losses']}

{emoji(ENDERIA_EMOJI['star'], '🎁')} <b>Ежедневный бонус: +100 алмазов</b>
📝 Добавь в описание: @lostearth_bot

{get_enderia_emojis(1)} Напиши /daily чтобы получить бонус! {get_enderia_emojis(1)}"""
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/daily"):
        if has_bot_in_bio:
            bonus_given, amount = check_and_add_bonus(username, True)
            if bonus_given:
                balance = get_balance(username)
                response = f"{emoji(ENDERIA_EMOJI['star'], '🎁')} ЕЖЕДНЕВНЫЙ БОНУС! {emoji(ENDERIA_EMOJI['star'], '🎁')}\n\n✨ +{amount} 💎 алмазов!\n💎 Баланс: {balance} алмазов\n\n{emoji(ENDERIA_EMOJI['anime_dance'], '🌸')} Заходи завтра снова! {emoji(ENDERIA_EMOJI['anime_dance'], '🌸')}"
            else:
                response = f"{get_enderia_emojis()} {username}, ты уже получал бонус сегодня! Возвращайся завтра! {emoji(ENDERIA_EMOJI['cat_sleep'], '🌸')}"
        else:
            response = f"""{emoji(ENDERIA_EMOJI['cat_surprised'], '❌')} <b>НЕТ БОНУСА!</b> {emoji(ENDERIA_EMOJI['cat_surprised'], '❌')}

Чтобы получать ежедневный бонус 100 алмазов, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

{get_enderia_emojis(1)} После добавления напиши /daily снова! {get_enderia_emojis(1)}"""
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/bet"):
        match = re.match(r"^/bet\s+(\d+)$", user_message)
        if match and bot and chat_id:
            bet_amount = int(match.group(1))
            response = await game_dice_bet(username, bet_amount, bot, chat_id)
        else:
            response = f"{get_enderia_emojis()} {username}, используй: /bet [сумма] (например /bet 50) 🎲\n💰 Минимальная ставка: 10 алмазов"
        add_to_memory(username, user_message, response)
        return response
    
    if user_message.startswith("/games"):
        response = f"""{emoji(ENDERIA_EMOJI['joystick'], '🎮')} <b>ДОСТУПНЫЕ ИГРЫ</b> {emoji(ENDERIA_EMOJI['joystick'], '🎮')}

💰 <b>/bet [сумма]</b> - Ставка на кубик (выигрыш x2)
💎 <b>/balance</b> - Показать баланс
👤 <b>/profile</b> - Твой профиль
🎁 <b>/daily</b> - Ежедневный бонус 100💎

✨ <b>Правила игры:</b>
• Минимальная ставка: 10 алмазов
• Твой кубик против моего
• Если твой кубик больше - выигрываешь x2

💎 <b>Стартовый баланс: 100 алмазов</b>

{get_enderia_emojis(1)} Напиши /bet 50 чтобы сыграть! {get_enderia_emojis(1)}"""
        add_to_memory(username, user_message, response)
        return response
    
    # ========== ОБЫЧНЫЙ РАЗГОВОР ==========
    history = get_user_context(username)
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # Если просто позвали по имени - отвечаем без лишних вопросов
    if is_name_call and not is_reply:
        response = f"{get_enderia_emojis()} Слушаю, {username}! Что хотел узнать? Может сыграем в кости? 🎲"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        return response
    
    # Если уже здоровались и снова привет - не здороваемся заново
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"{get_enderia_emojis()} {username}, мы уже общаемся! Хочешь сыграть в кости? Напиши /bet 50 🎲"
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
ВАЖНО: 
- Если вы уже общались - НЕ ЗДОРОВАЙСЯ заново!
- Если это ответ на твоё сообщение - ПРОДОЛЖАЙ ДИАЛОГ
- Будь милой, дружелюбной, используй эмодзи
- Отвечай 2-4 предложения
- Если спросят про игры - расскажи про /bet и /daily"""
            
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
                                "max_tokens": 500,
                                "temperature": 0.9,
                            },
                            timeout=aiohttp.ClientTimeout(total=35)
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
    
    # Fallback
    fallback = f"{get_enderia_emojis()} {username}, я здесь! Хочешь сыграть в кости? Напиши /bet 50 🎲\n\nЕжедневный бонус 100💎 за @lostearth_bot в описании! {get_enderia_emojis(1)}"
    add_to_memory(username, user_message, fallback)
    return fallback

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    # Отвечаем только когда обращаются к Эндерии
    keywords = ["эндер", "эндерия", "энди", "ендер", "енди", "@lostearth_bot"]
    return any(keyword in text_lower for keyword in keywords)
