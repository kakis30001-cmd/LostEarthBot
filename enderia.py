import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
from dotenv import load_dotenv

from prompts import get_system_prompt
from database import (
    init_db, get_balance, update_balance, can_claim_daily_bonus,
    claim_daily_bonus, update_stats, get_stats, create_player
)

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
    emojis = ["💜", "🐱", "🐰", "✨", "🎲", "🪙", "💎", "🎯", "🕹️", "⭐"]
    return random.choice(emojis)

# Анимированные кубики Telegram
def get_dice_animation(value: int):
    """Возвращает анимированный кубик Telegram"""
    dice_emojis = {
        1: "🎲", 2: "🎲", 3: "🎲", 4: "🎲", 5: "🎲", 6: "🎲"
    }
    return dice_emojis.get(value, "🎲")

async def roll_animated_dice(bot, chat_id: int, username: str, is_bot_turn: bool = False):
    """Отправляет анимированный кубик в чат и возвращает результат"""
    msg = await bot.send_dice(chat_id, emoji="🎲")
    value = msg.dice.value
    return value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    # Получаем баланс из БД
    balance = await get_balance(username)
    
    if balance < bet_amount:
        return f"{get_random_emoji()} {username}, у тебя всего {balance} алмазов! Не хватает на ставку {bet_amount} 💎"
    
    if bet_amount <= 0:
        return f"{get_random_emoji()} {username}, ставка должна быть больше 0! 🐱"
    
    # Бросаем анимированные кубики
    player_value = await roll_animated_dice(bot, chat_id, username, is_bot_turn=False)
    await asyncio.sleep(1.5)
    bot_value = await roll_animated_dice(bot, chat_id, "Эндерия", is_bot_turn=True)
    
    # Результат
    if player_value > bot_value:
        win_amount = bet_amount * 2
        await update_balance(username, bet_amount)
        await update_stats(username, is_win=True)
        
        # Генерируем реакцию Эндерии через ИИ
        reaction = await get_enderia_reaction("win", username, player_value, bot_value)
        
        return f"{get_random_emoji()} 🎲 ПОБЕДА! 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n✨ Ты выиграл {bet_amount} алмазов! +{bet_amount} 💎\nБаланс: {balance + bet_amount} 💎\n\n{reaction}"
        
    elif player_value < bot_value:
        await update_balance(username, -bet_amount)
        await update_stats(username, is_win=False)
        
        reaction = await get_enderia_reaction("lose", username, player_value, bot_value)
        
        return f"{get_random_emoji()} 🎲 ПРОИГРЫШ... 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n😔 Ты проиграл {bet_amount} алмазов! -{bet_amount} 💎\nБаланс: {balance - bet_amount} 💎\n\n{reaction}"
    else:
        reaction = await get_enderia_reaction("draw", username, player_value, bot_value)
        
        return f"{get_random_emoji()} 🎲 НИЧЬЯ! 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n🤝 Ставка возвращена! {bet_amount} 💎\nБаланс: {balance} 💎\n\n{reaction}"

async def game_dice_battle(username: str, bot, chat_id: int) -> str:
    player_value = await roll_animated_dice(bot, chat_id, username, is_bot_turn=False)
    await asyncio.sleep(1.5)
    bot_value = await roll_animated_dice(bot, chat_id, "Эндерия", is_bot_turn=True)
    
    if player_value > bot_value:
        reaction = await get_enderia_reaction("win_battle", username, player_value, bot_value)
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n✨ Ты победил! ✨\n\n{reaction}"
    elif player_value < bot_value:
        reaction = await get_enderia_reaction("lose_battle", username, player_value, bot_value)
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n💔 Я победила! 💔\n\n{reaction}"
    else:
        reaction = await get_enderia_reaction("draw_battle", username, player_value, bot_value)
        return f"{get_random_emoji()} 🎲 БИТВА КУБИКОВ 🎲 {get_random_emoji()}\n\n{username}: {get_dice_animation(player_value)} {player_value}\nЭндерия: {get_dice_animation(bot_value)} {bot_value}\n\n🤝 Ничья! 🤝\n\n{reaction}"

async def get_enderia_reaction(result_type: str, username: str, player_value: int, bot_value: int) -> str:
    """Генерирует реакцию Эндерии через ИИ"""
    if not OPENROUTER_API_KEY:
        reactions = {
            "win": [f"{get_random_emoji()} Поздравляю, {username}! Ты сильнее меня в этот раз! {get_random_emoji()}", 
                    f"{get_random_emoji()} Ух, какой удачный бросок! {username}, ты сегодня везучий! {get_random_emoji()}"],
            "lose": [f"{get_random_emoji()} Ха-ха! {username}, в следующий раз повезёт! {get_random_emoji()}",
                     f"{get_random_emoji()} Я же говорила, что я чемпион по кубикам! {get_random_emoji()}"],
            "draw": [f"{get_random_emoji()} Ничья! {username}, давай сыграем ещё? {get_random_emoji()}",
                     f"{get_random_emoji()} Равные силы! {username}, реванш? {get_random_emoji()}"]
        }
        return random.choice(reactions.get(result_type, [f"{get_random_emoji()} Хорошая игра, {username}! {get_random_emoji()}"]))
    
    try:
        prompts = {
            "win": f"Ты проиграла в кости игроку {username}. Напиши коротко (1 предложение) как проигравшая, но милая эндермен-девушка. Используй эмодзи.",
            "lose": f"Ты выиграла в кости у игрока {username}. Напиши коротко (1 предложение) радостную победную фразу как милая эндермен-девушка. Используй эмодзи.",
            "draw": f"У вас ничья в кости с игроком {username}. Напиши коротко (1 предложение) предлагая сыграть ещё. Используй эмодзи."
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-oss-120b",
                    "messages": [{"role": "user", "content": prompts.get(result_type, "")}],
                    "max_tokens": 50,
                    "temperature": 0.9,
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
    except:
        pass
    
    return f"{get_random_emoji()} Отличная игра, {username}! {get_random_emoji()}"

# Остальные функции (память, угадай число и т.д.) остаются теми же
# ... (добавь сюда остальные функции из предыдущей версии)

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "энд"]
    return any(keyword in text_lower for keyword in keywords)
