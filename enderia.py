import os
import random
import re
import asyncio
import json
from datetime import datetime, date
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

# ========== ФАЙЛОВОЕ ХРАНИЛИЩЕ ==========
PLAYERS_FILE = "players.json"

# Фермы
FARMS = {
    "пауков": {"base_income": 50, "emoji": "🕷️", "cost": 1000},
    "зомби": {"base_income": 75, "emoji": "🧟", "cost": 1000},
    "криперов": {"base_income": 100, "emoji": "💥", "cost": 1000},
    "скелетов": {"base_income": 60, "emoji": "🏹", "cost": 1000},
    "эндерменов": {"base_income": 150, "emoji": "👾", "cost": 1500},
}

UPGRADE_COSTS = {1: 0, 2: 500, 3: 1000, 4: 2000, 5: 5000}

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

def init_player(username: str):
    data = load_players()
    if username not in data:
        data[username] = {
            "xp": 1000,  # опыт вместо алмазов
            "last_bonus": None,
            "wins": 0,
            "losses": 0,
            "farms": {},
            "last_claim": str(datetime.now().timestamp())
        }
        save_players(data)
    return data[username]

def get_xp(username: str) -> int:
    data = load_players()
    if username not in data:
        init_player(username)
        return 1000
    return data[username].get("xp", 1000)

def update_xp(username: str, delta: int):
    data = load_players()
    if username not in data:
        init_player(username)
    data[username]["xp"] = data[username].get("xp", 1000) + delta
    save_players(data)

def get_stats(username: str) -> dict:
    data = load_players()
    if username not in data:
        return {"wins": 0, "losses": 0}
    return {"wins": data[username].get("wins", 0), "losses": data[username].get("losses", 0)}

def update_stats(username: str, is_win: bool):
    data = load_players()
    if username not in data:
        init_player(username)
    if is_win:
        data[username]["wins"] = data[username].get("wins", 0) + 1
    else:
        data[username]["losses"] = data[username].get("losses", 0) + 1
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
        init_player(username)
    data[username]["xp"] = data[username].get("xp", 1000) + 500
    data[username]["last_bonus"] = str(date.today())
    save_players(data)
    return 500

# ========== ФЕРМЫ ==========
def get_farms(username: str) -> dict:
    data = load_players()
    if username not in data:
        init_player(username)
    return data[username].get("farms", {})

def buy_farm(username: str, farm_name: str) -> tuple[bool, str]:
    if farm_name not in FARMS:
        return False, "Такой фермы нет!"
    
    farms = get_farms(username)
    if farm_name in farms:
        return False, f"Ферма {farm_name} уже есть!"
    
    cost = FARMS[farm_name]["cost"]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"Не хватает опыта! Нужно {cost} XP, у тебя {xp}"
    
    update_xp(username, -cost)
    farms[farm_name] = {"level": 1, "last_claim": str(datetime.now().timestamp())}
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    return True, f"Купил ферму {farm_name}! Уровень 1"

def upgrade_farm(username: str, farm_name: str) -> tuple[bool, str]:
    farms = get_farms(username)
    if farm_name not in farms:
        return False, "У тебя нет этой фермы!"
    
    current_level = farms[farm_name]["level"]
    if current_level >= 5:
        return False, "Максимальный уровень 5!"
    
    cost = UPGRADE_COSTS[current_level + 1]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"Не хватает опыта! Нужно {cost} XP"
    
    update_xp(username, -cost)
    farms[farm_name]["level"] = current_level + 1
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    return True, f"Ферма {farm_name} улучшена до {current_level + 1} уровня!"

def calculate_income(farms: dict) -> int:
    total = 0
    for farm_name, farm_data in farms.items():
        if farm_name in FARMS:
            base = FARMS[farm_name]["base_income"]
            level = farm_data.get("level", 1)
            total += base * level
    return total

def claim_income(username: str) -> int:
    farms = get_farms(username)
    if not farms:
        return 0
    
    now = datetime.now()
    total_income = 0
    
    data = load_players()
    for farm_name, farm_data in farms.items():
        last_claim = datetime.fromtimestamp(float(farm_data.get("last_claim", now.timestamp())))
        hours_passed = (now - last_claim).total_seconds() / 3600
        
        if hours_passed > 0:
            base = FARMS[farm_name]["base_income"]
            level = farm_data.get("level", 1)
            income = int(base * level * min(hours_passed, 24))
            total_income += income
            farm_data["last_claim"] = str(now.timestamp())
    
    if total_income > 0:
        update_xp(username, total_income)
        data[username]["farms"] = farms
        save_players(data)
    
    return total_income

def get_leaderboard(limit: int = 10) -> list:
    data = load_players()
    players = []
    for username, info in data.items():
        players.append({
            "username": username,
            "xp": info.get("xp", 0),
            "wins": info.get("wins", 0),
            "farms_count": len(info.get("farms", {}))
        })
    players.sort(key=lambda x: x["xp"], reverse=True)
    return players[:limit]

# ========== ОСТАЛЬНОЙ КОД ==========
current_online = 0
current_max = 0
user_memory = defaultdict(lambda: deque(maxlen=20))
user_greeted = {}
last_active = {}
last_spontaneous_message = {}

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "Эндерия" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"{username}: {user_message}")
    user_memory[username].append(f"Эндерия: {bot_response}")

def clear_user_memory(username: str):
    if username in user_memory:
        user_memory[username].clear()

def get_memory_size(username: str) -> int:
    return len(user_memory.get(username, [])) // 2

def has_already_greeted(username: str) -> bool:
    return user_greeted.get(username, False)

def mark_greeted(username: str):
    user_greeted[username] = True

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "эндер", "эндерия", "ендер", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names

async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

async def game_dice_bet(username: str, bet_amount: int, bot, chat_id: int) -> str:
    xp = get_xp(username)
    if xp < bet_amount:
        return f"😔 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount}"
    
    if bet_amount < 50:
        return f"🎲 {username}, минимальная ставка 50 XP!"
    
    await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
    player_value = await roll_dice_animated(bot, chat_id)
    
    await asyncio.sleep(1.5)
    await bot.send_message(chat_id, f"🐱 Эндерия бросает кубик...")
    bot_value = await roll_dice_animated(bot, chat_id)
    
    if player_value > bot_value:
        update_xp(username, bet_amount)
        update_stats(username, is_win=True)
        new_xp = get_xp(username)
        return f"🎉 ПОБЕДА! 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {bet_amount} XP!\n💎 Баланс: {new_xp} XP"
    elif player_value < bot_value:
        update_xp(username, -bet_amount)
        update_stats(username, is_win=False)
        new_xp = get_xp(username)
        return f"😔 ПРОИГРЫШ...\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} XP!\n💎 Баланс: {new_xp} XP"
    else:
        return f"🤝 НИЧЬЯ!\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💎 Баланс: {xp} XP"

async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None, user_bio: str = "") -> str:
    save_to_log(username, user_message, is_bot=False)
    
    # Обновляем время последней активности
    last_active[username] = datetime.now()
    
    msg_lower = user_message.lower()
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    # Команды
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        xp = get_xp(username)
        return f"👑 {username}, твой баланс: {xp} XP! 🎮"
    
    if user_message.startswith("/profile"):
        xp = get_xp(username)
        stats = get_stats(username)
        farms = get_farms(username)
        farm_count = len(farms)
        total_income = calculate_income(farms)
        
        text = f"""👑 ПРОФИЛЬ ИГРОКА 👑

Имя: {username}
💎 Опыт: {xp} XP
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
🏭 Ферм: {farm_count}
📈 Доход в час: {total_income} XP

✨ Ежедневный бонус: +500 XP
📝 Добавь в описание: @lostearth_bot

/farms - управление фермами
/daily - получить бонус"""
        return text
    
    if user_message.startswith("/daily"):
        if has_bot_in_bio:
            if can_claim_daily_bonus(username):
                amount = claim_daily_bonus(username)
                xp = get_xp(username)
                return f"🎁 ЕЖЕДНЕВНЫЙ БОНУС! 🎁\n\n✨ +{amount} XP!\n💎 Баланс: {xp} XP\n\n🐰 Заходи завтра снова!"
            else:
                return f"💜 {username}, ты уже получал бонус сегодня! Возвращайся завтра!"
        else:
            return f"""❌ НЕТ БОНУСА!

Добавь в описание профиля: @lostearth_bot

📝 Как это сделать:
1. Настройки Telegram → фото профиля
2. Редактировать профиль → Описание
3. Добавь: @lostearth_bot
4. Сохрани и напиши /daily снова!"""
    
    if user_message.startswith("/farms"):
        farms = get_farms(username)
        if not farms:
            return f"""🏭 У тебя пока нет ферм!

Доступные фермы:
🕷️ Пауки - 1000 XP (50/час)
🧟 Зомби - 1000 XP (75/час)
💥 Криперы - 1000 XP (100/час)
🏹 Скелеты - 1000 XP (60/час)
👾 Эндермены - 1500 XP (150/час)

/buy_farm <название> - купить ферму
/claim - собрать опыт"""
        
        text = "🏭 ТВОИ ФЕРМЫ 🏭\n\n"
        for name, data in farms.items():
            farm_info = FARMS[name]
            level = data.get("level", 1)
            income = farm_info["base_income"] * level
            text += f"{farm_info['emoji']} {name}: ур. {level} ({income} XP/час)\n"
        
        total = calculate_income(farms)
        text += f"\n📈 Общий доход: {total} XP/час\n/claim - собрать опыт"
        return text
    
    if user_message.startswith("/buy_farm"):
        parts = user_message.split(maxsplit=1)
        if len(parts) < 2:
            return "Используй: /buy_farm <название>\nДоступны: пауков, зомби, криперов, скелетов, эндерменов"
        
        farm_name = parts[1].lower()
        # Нормализация названия
        for key in FARMS:
            if key in farm_name:
                success, msg = buy_farm(username, key)
                return msg
        return "Ферма не найдена! Доступны: пауков, зомби, криперов, скелетов, эндерменов"
    
    if user_message.startswith("/upgrade_farm"):
        parts = user_message.split(maxsplit=1)
        if len(parts) < 2:
            return "Используй: /upgrade_farm <название>"
        
        farm_name = parts[1].lower()
        for key in FARMS:
            if key in farm_name:
                success, msg = upgrade_farm(username, key)
                return msg
        return "Ферма не найдена!"
    
    if user_message.startswith("/claim"):
        income = claim_income(username)
        if income > 0:
            xp = get_xp(username)
            return f"💰 Собрано {income} XP с ферм!\n💎 Твой опыт: {xp} XP"
        else:
            return "🍃 Пока не накопилось опыта с ферм. Подожди немного или улучшай фермы!"
    
    if user_message.startswith("/leaderboard") or user_message.startswith("/top"):
        leaders = get_leaderboard(10)
        text = "👑 ТОП ИГРОКОВ ПО ОПЫТУ 👑\n\n"
        for i, p in enumerate(leaders, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
            text += f"{medal} {p['username']} - {p['xp']} XP (ферм: {p['farms_count']})\n"
        return text
    
    if user_message.startswith("/bet"):
        match = re.match(r"^/bet\s+(\d+)$", user_message)
        if match and bot and chat_id:
            bet_amount = int(match.group(1))
            return await game_dice_bet(username, bet_amount, bot, chat_id)
        return f"🎲 Используй: /bet [сумма] (мин 50 XP)"
    
    if user_message.startswith("/games"):
        return f"""🎮 ДОСТУПНЫЕ ИГРЫ 🎮

🎲 /bet [сумма] - игра в кости (выигрыш x2)
👑 /balance - баланс опыта
👤 /profile - твой профиль
🎁 /daily - бонус 500 XP

🏭 ФЕРМЫ ОПЫТА:
/farms - твои фермы
/buy_farm - купить ферму
/upgrade_farm - улучшить ферму
/claim - собрать опыт
/leaderboard - топ игроков

💎 Стартовый баланс: 1000 XP"""
    
    # Обычный диалог (без постоянного предложения игр)
    history = "\n".join(list(user_memory[username])[-10:]) if username in user_memory else ""
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # Если позвали по имени
    if is_name_call and not is_reply:
        response = f"🐱 Слушаю, {username}! Чем могу помочь? /farms или /games?"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        return response
    
    # Простые ответы без ИИ для частых вопросов
    if "онлайн" in msg_lower or "сколько народу" in msg_lower:
        return f"👑 Сейчас на сервере {current_online}/{current_max} игроков! Заходи, будет весело! 🎮"
    
    if "ферм" in msg_lower or "фарм" in msg_lower:
        farms = get_farms(username)
        if farms:
            total = calculate_income(farms)
            return f"🏭 Твои фермы приносят {total} XP в час! Не забывай собирать /claim"
        return f"🏭 У тебя нет ферм! Купи первую за /buy_farm пауков (1000 XP)"
    
    if "сервер" in msg_lower:
        return f"🌍 LostEarth — Minecraft сервер 1.21-1.26+\nIP: 150.241.85.40:25565\nРежимы: Мирный (PvE) и SMP (PvP)"
    
    if "кто ты" in msg_lower:
        return f"💜 Я Эндерия — девушка-эндермен, хранительница Края! Сама играю на сервере, фармлю криперов 😊"
    
    # Fallback для остального
    responses = [
        f"🐱 {username}, я тут! Что интересного на фермах?",
        f"✨ {username}, телепортнулась к тебе! Рассказывай, как дела?",
        f"💜 {username}, я сейчас криперов фармила, а ты чем занят?",
        f"🏭 {username}, не забывай собирать опыт с ферм командой /claim!"
    ]
    
    response = random.choice(responses)
    if not already_greeted:
        mark_greeted(username)
    add_to_memory(username, user_message, response)
    return response

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "енди", "@lostearth_bot"]
    return any(keyword in text_lower for keyword in keywords)

async def spontaneous_message_checker(bot, chat_id: int):
    """Проверяет, нужно ли отправить спонтанное сообщение"""
    while True:
        await asyncio.sleep(1800)  # 30 минут
        
        now = datetime.now()
        # Проверяем активность за последние 30 минут
        active_users = []
        for user, last in last_active.items():
            if (now - last).total_seconds() < 3600:
                active_users.append(user)
        
        if active_users and current_online > 0:
            messages = [
                f"🐱 Народ, как дела на фермах? Я уже 1000 XP накопила!",
                f"✨ Что молчим? Пойдёмте вместе фармить эндерменов!",
                f"💜 Эй, игроки! Кто хочет сыграть в кости? /bet 100",
                f"🏭 Как успехи? У кого какая ферма самая крутая?",
                f"👑 На сервере {current_online} игроков! Заходите, вместе веселее!"
            ]
            await bot.send_message(chat_id, random.choice(messages), parse_mode="HTML")
