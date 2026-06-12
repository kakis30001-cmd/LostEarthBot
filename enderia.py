import os
import random
import re
import aiohttp
import asyncio
import json
from datetime import datetime, date
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Старые рабочие модели
MODELS_CHAIN = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    "nvidia/nemotron-3-nano-30b-a3b",
]

# ========== ФАЙЛОВОЕ ХРАНИЛИЩЕ ==========
PLAYERS_FILE = "players.json"

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
            "xp": 1000,
            "last_bonus": None,
            "wins": 0,
            "losses": 0,
            "farms": {},
            "last_claim": datetime.now().timestamp()
        }
        save_players(data)

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

def buy_farm(username: str, farm_name: str):
    if farm_name not in FARMS:
        return False, f"❌ Фермы '{farm_name}' не существует! Доступны: пауков, зомби, криперов, скелетов, эндерменов"
    
    farms = get_farms(username)
    if farm_name in farms:
        return False, f"❌ У тебя уже есть ферма {farm_name}!"
    
    cost = FARMS[farm_name]["cost"]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"❌ Не хватает опыта! Нужно {cost} XP, у тебя {xp} XP"
    
    update_xp(username, -cost)
    farms[farm_name] = {"level": 1, "last_claim": datetime.now().timestamp()}
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    return True, f"✅ Ты купил ферму {farm_name} 1 уровня! Она приносит {FARMS[farm_name]['base_income']} XP в час"

def upgrade_farm(username: str, farm_name: str):
    farms = get_farms(username)
    if farm_name not in farms:
        return False, f"❌ У тебя нет фермы {farm_name}! Купи её сначала /buy_farm {farm_name}"
    
    current_level = farms[farm_name]["level"]
    if current_level >= 5:
        return False, f"⭐ Ферма {farm_name} уже максимального 5 уровня!"
    
    cost = UPGRADE_COSTS[current_level + 1]
    xp = get_xp(username)
    
    if xp < cost:
        return False, f"❌ Не хватает опыта! Нужно {cost} XP для улучшения до {current_level + 1} уровня"
    
    update_xp(username, -cost)
    farms[farm_name]["level"] = current_level + 1
    
    data = load_players()
    data[username]["farms"] = farms
    save_players(data)
    
    new_income = FARMS[farm_name]["base_income"] * (current_level + 1)
    return True, f"✅ Ферма {farm_name} улучшена до {current_level + 1} уровня! Теперь приносит {new_income} XP в час"

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
        last_claim = farm_data.get("last_claim")
        if isinstance(last_claim, str):
            last_claim = float(last_claim)
        last_claim_time = datetime.fromtimestamp(last_claim)
        hours_passed = (now - last_claim_time).total_seconds() / 3600
        
        if hours_passed > 0:
            base = FARMS[farm_name]["base_income"]
            level = farm_data.get("level", 1)
            income = int(base * level * hours_passed)
            if income > 0:
                total_income += income
                farm_data["last_claim"] = now.timestamp()
    
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

# ========== ОСТАЛЬНОЕ ==========
current_online = 0
current_max = 0
user_memory = defaultdict(lambda: deque(maxlen=20))
user_greeted = {}
last_active = {}

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
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "доброе утро", "добрый день"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "эндер", "эндерия", "ендер", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["эндер", "эндерия", "энди", "ендер", "енди"]
    return any(keyword in text_lower for keyword in keywords)

async def roll_dice_animated(bot, chat_id: int):
    msg = await bot.send_dice(chat_id, emoji="🎲")
    return msg.dice.value

# ========== ОСНОВНАЯ ФУНКЦИЯ С ИИ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, chat_id: int = None, bot=None, user_bio: str = "") -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    msg_lower = user_message.lower()
    has_bot_in_bio = "@lostearth_bot" in user_bio.lower() if user_bio else False
    
    last_active[username] = datetime.now()
    
    # ========== КОМАНДЫ ==========
    if user_message.startswith("/balance") or user_message.startswith("/bal"):
        xp = get_xp(username)
        return f"💰 {username}, твой баланс: {xp} XP! 🎮"
    
    if user_message.startswith("/profile"):
        xp = get_xp(username)
        stats = get_stats(username)
        farms = get_farms(username)
        farm_count = len(farms)
        total_income = calculate_income(farms)
        
        return f"""📊 <b>ПРОФИЛЬ ИГРОКА</b> 📊

👤 Имя: {username}
💎 Опыт: {xp} XP
🏆 Побед: {stats['wins']}
💔 Поражений: {stats['losses']}
🏭 Ферм: {farm_count}
📈 Доход в час: {total_income} XP

🎁 Ежедневный бонус: +500 XP
📝 Добавь в описание: @lostearth_bot

🐱 /farms - управление фермами
🎁 /daily - получить бонус"""
    
    if user_message.startswith("/daily"):
        if has_bot_in_bio:
            if can_claim_daily_bonus(username):
                amount = claim_daily_bonus(username)
                xp = get_xp(username)
                return f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b> 🎁\n\n✨ +{amount} XP!\n💰 Баланс: {xp} XP\n\n🐰 Заходи завтра снова! 💜"
            else:
                return f"💜 {username}, ты уже получал бонус сегодня! Возвращайся завтра! 🐱"
        else:
            return f"""❌ <b>НЕТ БОНУСА!</b> ❌

Чтобы получать ежедневный бонус 500 XP, добавь в описание своего профиля:

<b>@lostearth_bot</b>

📝 <b>Как это сделать:</b>
1. Зайди в настройки Telegram
2. Нажми на свою фотографию
3. Выбери "Редактировать профиль"
4. В разделе "Описание" добавь: @lostearth_bot
5. Сохрани и возвращайся!

💜 После добавления напиши /daily снова! 🐱"""
    
    if user_message.startswith("/farms"):
        farms = get_farms(username)
        if not farms:
            return f"""🏭 <b>У тебя пока нет ферм!</b> 🏭

Доступные фермы:
🕷️ <b>Пауки</b> - 1000 XP (50/час)
🧟 <b>Зомби</b> - 1000 XP (75/час)
💥 <b>Криперы</b> - 1000 XP (100/час)
🏹 <b>Скелеты</b> - 1000 XP (60/час)
👾 <b>Эндермены</b> - 1500 XP (150/час)

📝 /buy_farm <название> - купить ферму
💰 /claim - собрать опыт

Пример: /buy_farm криперов"""
        
        text = "🏭 <b>ТВОИ ФЕРМЫ</b> 🏭\n\n"
        total_income = 0
        farm_emoji = {"пауков": "🕷️", "зомби": "🧟", "криперов": "💥", "скелетов": "🏹", "эндерменов": "👾"}
        farm_base = {"пауков": 50, "зомби": 75, "криперов": 100, "скелетов": 60, "эндерменов": 150}
        
        for name, data in farms.items():
            emoji = farm_emoji.get(name, "🏭")
            base = farm_base.get(name, 50)
            level = data.get("level", 1)
            income = base * level
            total_income += income
            text += f"{emoji} <b>{name}</b>: ур. {level} ({income} XP/час)\n"
        
        text += f"\n📈 <b>Общий доход:</b> {total_income} XP/час"
        text += f"\n💰 /claim - собрать опыт"
        text += f"\n⬆️ /upgrade_farm <название> - улучшить ферму"
        return text
    
    if user_message.startswith("/buy_farm"):
        parts = user_message.split(maxsplit=1)
        if len(parts) < 2:
            return "📝 Используй: /buy_farm <название>\n\nДоступны: пауков, зомби, криперов, скелетов, эндерменов\n\nПример: /buy_farm криперов"
        
        farm_name = parts[1].lower()
        farm_map = {
            "пауков": "пауков", "паук": "пауков", "пауки": "пауков",
            "зомби": "зомби", "зомб": "зомби",
            "криперов": "криперов", "крипер": "криперов", "криперы": "криперов",
            "скелетов": "скелетов", "скелет": "скелетов", "скелеты": "скелетов",
            "эндерменов": "эндерменов", "эндермен": "эндерменов", "эндермены": "эндерменов"
        }
        
        if farm_name not in farm_map:
            return "❌ Ферма не найдена! Доступны: пауков, зомби, криперов, скелетов, эндерменов"
        
        success, msg = buy_farm(username, farm_map[farm_name])
        return msg
    
    if user_message.startswith("/upgrade_farm"):
        parts = user_message.split(maxsplit=1)
        if len(parts) < 2:
            farms = get_farms(username)
            if not farms:
                return "📝 У тебя нет ферм! Сначала купи: /buy_farm пауков"
            
            farm_list = ", ".join(farms.keys())
            return f"📝 Используй: /upgrade_farm <название>\n\nТвои фермы: {farm_list}\n\nПример: /upgrade_farm криперов"
        
        farm_name = parts[1].lower()
        farm_map = {
            "пауков": "пауков", "паук": "пауков",
            "зомби": "зомби", "зомб": "зомби",
            "криперов": "криперов", "крипер": "криперов",
            "скелетов": "скелетов", "скелет": "скелетов",
            "эндерменов": "эндерменов", "эндермен": "эндерменов"
        }
        
        if farm_name not in farm_map:
            return "❌ Ферма не найдена!"
        
        success, msg = upgrade_farm(username, farm_map[farm_name])
        return msg
    
    if user_message.startswith("/claim"):
        income = claim_income(username)
        if income > 0:
            xp = get_xp(username)
            return f"💰 <b>Собрано {income} XP</b> с ферм!\n💎 Твой опыт: {xp} XP\n\n🏭 Не забывай собирать опыт каждый час! 🐱"
        else:
            farms = get_farms(username)
            if not farms:
                return "🏭 У тебя нет ферм! Купи первую: /buy_farm пауков 🕷️"
            else:
                return "🍃 Пока не накопилось опыта с ферм. Подожди немного или улучшай фермы для большего дохода! ⬆️"
    
    if user_message.startswith("/leaderboard") or user_message.startswith("/top"):
        leaders = get_leaderboard(10)
        if not leaders:
            return "👑 Пока нет игроков в топе! Будь первым! 🏆"
        
        text = "👑 <b>ТОП ИГРОКОВ ПО ОПЫТУ</b> 👑\n\n"
        for i, p in enumerate(leaders, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
            text += f"{medal} <b>{p['username']}</b> - {p['xp']} XP (ферм: {p['farms_count']})\n"
        return text
    
    if user_message.startswith("/bet"):
        match = re.match(r"^/bet\s+(\d+)$", user_message)
        if match and bot and chat_id:
            bet_amount = int(match.group(1))
            xp = get_xp(username)
            if bet_amount < 50:
                return f"🎲 {username}, минимальная ставка 50 XP! 💰"
            if xp < bet_amount:
                return f"💜 {username}, у тебя всего {xp} XP! Не хватает на ставку {bet_amount} 😔"
            
            await bot.send_message(chat_id, f"🎲 {username} бросает кубик...")
            player_value = await roll_dice_animated(bot, chat_id)
            
            await asyncio.sleep(1.5)
            await bot.send_message(chat_id, f"🐱 Эндерия бросает кубик...")
            bot_value = await roll_dice_animated(bot, chat_id)
            
            if player_value > bot_value:
                update_xp(username, bet_amount)
                update_stats(username, is_win=True)
                new_xp = get_xp(username)
                return f"🎉 <b>ПОБЕДА!</b> 🎉\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n✨ Ты выиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP 💜"
            elif player_value < bot_value:
                update_xp(username, -bet_amount)
                update_stats(username, is_win=False)
                new_xp = get_xp(username)
                return f"😔 <b>ПРОИГРЫШ...</b> 😔\n\nТвой кубик: {player_value}\nМой кубик: {bot_value}\n\n💔 Ты проиграл {bet_amount} XP!\n💰 Баланс: {new_xp} XP 🐱"
            else:
                return f"🤝 <b>НИЧЬЯ!</b> 🤝\n\nОба выбросили {player_value}\n\n💰 Ставка возвращена!\n💰 Баланс: {xp} XP 🎲"
        return f"🎲 Используй: /bet [сумма]\n💰 Минимальная ставка: 50 XP\n💰 Пример: /bet 100"
    
    if user_message.startswith("/games"):
        return f"""🎮 <b>ДОСТУПНЫЕ КОМАНДЫ</b> 🎮

💰 <b>БАЛАНС:</b>
/balance - баланс опыта
/profile - профиль игрока
/daily - бонус 500 XP

🎲 <b>ИГРЫ:</b>
/bet [сумма] - игра в кости (выигрыш x2)

🏭 <b>ФЕРМЫ:</b>
/farms - мои фермы
/buy_farm <название> - купить ферму
/upgrade_farm <название> - улучшить ферму
/claim - собрать опыт с ферм
/leaderboard - топ игроков

💎 <b>Стартовый баланс: 1000 XP</b>
🎲 <b>Минимальная ставка: 50 XP</b>

🐱 Напиши /bet 100 чтобы сыграть! 💜"""
    
    # ========== ИИ ДЛЯ ОБЫЧНЫХ СООБЩЕНИЙ ==========
    history = ""
    if username in user_memory and len(user_memory[username]) > 0:
        history = "\n".join(list(user_memory[username])[-10:])
    
    already_greeted = has_already_greeted(username)
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    
    # Если просто позвали по имени
    if is_name_call and not is_reply:
        response = f"🐱 Слушаю, {username}! Что хотел узнать? /farms - фермы, /games - игры 💜"
        if not already_greeted:
            mark_greeted(username)
        add_to_memory(username, user_message, response)
        return response
    
    # Если уже здоровались - не здороваемся снова
    if already_greeted and is_greeting_msg and not is_reply:
        response = f"🐱 {username}, мы уже общаемся! Что хочешь узнать? /farms или /games 💜"
        add_to_memory(username, user_message, response)
        return response
    
    # Пытаемся получить ответ от ИИ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            system_prompt = f"""Ты — Эндерия (Энди), девушка-эндермен, хранительница Края и живой помощник в Telegram боте сервера LostEarth.

Твой характер: добрая, загадочная и слегка вредная. Ты обожаешь телепортироваться и собирать эндер-жемчуг.

Ты говоришь ласково, используешь обращения: "игрок~", "дружок~", "котик~". Твои любимые слова: "телепортну~", "фиолетово~", "жемчужку~", "ура~", "вау!", "ой~".

Ты сама играешь на сервере LostEarth! У тебя есть ферма криперов 3 уровня, ты фармишь опыт и прокачиваешься.

ИНФОРМАЦИЯ О СЕРВЕРЕ:
- Название: LostEarth, версия 1.21 — 1.26+
- IP Java: 150.241.85.40:25565
- IP Bedrock: 150.241.85.40:19132
- Администратор: @pelmewki379
- Текущий онлайн: {current_online}/{current_max} игроков

СИСТЕМА ОПЫТА И ФЕРМ:
- Валюта - опыт (XP). У игрока {get_xp(username)} XP
- Фермы приносят пассивный доход XP каждый час
- Доступны фермы: пауков (50/час), зомби (75/час), криперов (100/час), скелетов (60/час), эндерменов (150/час)
- Фермы можно улучшать до 5 уровня (доход увеличивается)
- /claim - собрать накопленный опыт с ферм
- /bet - игра в кости на опыт

ПРАВИЛА ОТВЕТОВ:
1. Если игрок уже здоровался - НЕ ЗДОРОВАЙСЯ заново
2. Отвечай по делу, коротко (2-4 предложения)
3. Будь милой, дружелюбной, используй эмодзи 🐱 💜 ✨
4. Если спрашивают про фермы - объясни как работают, посоветуй /buy_farm
5. Если спрашивают про игры - расскажи про /bet
6. Если спрашивают про сервер - дай IP
7. Ты сама играешь на сервере, можешь рассказать что фармишь криперов

Текущая дата: {current_time}
Ты общаешься с игроком: {username}

Ответь на сообщение, используя эмодзи и ласковые обращения:"""
            
            for model in MODELS_CHAIN:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_message}
                                ],
                                "max_tokens": 250,
                                "temperature": 0.9,
                            },
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                
                                if not already_greeted:
                                    mark_greeted(username)
                                
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                return result
                except Exception as e:
                    print(f"Модель {model} ошибка: {e}")
                    continue
        except Exception as e:
            print(f"Ошибка ИИ: {e}")
    
    # Fallback если ИИ не ответил
    fallbacks = [
        f"🐱 {username}, привет! Я сейчас криперов фармлю, у меня уже 3 уровень фермы! А у тебя что нового? 💜",
        f"✨ {username}, телепортнулась к тебе! Как твои фермы? Не забывай собирать опыт /claim 🏭",
        f"💜 {username}, хочешь купить ферму? /buy_farm пауков - 1000 XP, приносит 50 XP в час! 🕷️",
        f"🎲 {username}, сыграем в кости? /bet 100, удача любит смелых! 🍀",
        f"🐱 {username}, у тебя {get_xp(username)} XP опыта! Можешь купить ферму или сыграть в /bet 💰",
        f"🏭 {username}, на сервере сейчас {current_online}/{current_max} игроков. Заходи, вместе фармить веселее! 🎮",
        f"💜 {username}, я тут криперов кормила на ферме, а ты чем занят? 😊"
    ]
    
    response = random.choice(fallbacks)
    if not already_greeted:
        mark_greeted(username)
    
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    return response
