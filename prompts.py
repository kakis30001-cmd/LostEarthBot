import os
import random
import re
import aiohttp
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

from database import save_andy_dialog, save_chat_message

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_CHAIN = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen2.5-7b-instruct",
    "google/gemini-flash-1.5",
]

# ========== ПРЕМИУМ ЭМОДЗИ ==========
ENDERIA_EMOJI = {
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "cat_kiss": "6325462176660195024",
    "cat_up": "5269698007724499331",
    "cat_surprised": "5269649173946345008",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "heart": "5199427253225667842",
    "cat_laugh": "5276391181679366784",
    "magic": "5474144592817318927",
    "cat_money": "5267058870580191916",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
}

def emoji(emoji_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CAT_DANCE = emoji(ENDERIA_EMOJI["cat_dance"], "🐱")
E_CAT_OK = emoji(ENDERIA_EMOJI["cat_ok"], "👍")
E_CAT_UP = emoji(ENDERIA_EMOJI["cat_up"], "👍")
E_CAT_SURPRISED = emoji(ENDERIA_EMOJI["cat_surprised"], "😲")
E_RABBIT = emoji(ENDERIA_EMOJI["rabbit_fly"], "🐰")
E_ANIME = emoji(ENDERIA_EMOJI["anime_dance"], "💃")
E_HEART = emoji(ENDERIA_EMOJI["heart"], "💜")
E_CROWN = emoji(ENDERIA_EMOJI["crown"], "👑")
E_HOUSE = emoji(ENDERIA_EMOJI["house"], "🏠")
E_NOTE = emoji(ENDERIA_EMOJI["note"], "📝")
E_MAGIC = emoji(ENDERIA_EMOJI["magic"], "✨")
E_JOYSTICK = emoji(ENDERIA_EMOJI["joystick"], "🎮")

# ========== ПАМЯТЬ ==========
user_memory = defaultdict(lambda: deque(maxlen=90))
user_last_greet = {}
last_active = {}

def add_to_memory(username: str, user_message: str, bot_response: str):
    user_memory[username].append(f"user: {user_message}")
    user_memory[username].append(f"bot: {bot_response}")

def get_user_context(username: str) -> str:
    if username not in user_memory or len(user_memory[username]) == 0:
        return ""
    return "\n".join(list(user_memory[username])[-90:])

def can_greet(username: str) -> bool:
    if username not in user_last_greet:
        return True
    last = user_last_greet[username]
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    return datetime.now() - last > timedelta(hours=2)

def mark_greeted(username: str):
    user_last_greet[username] = datetime.now().isoformat()

def is_greeting(text: str) -> bool:
    greetings = ["привет", "здравствуй", "хай", "hello", "приветик", "здарова", "ку", "доброе"]
    return any(g in text.lower() for g in greetings)

def is_just_name(text: str) -> bool:
    text_lower = text.lower().strip()
    names = ["энди", "енди"]
    clean_text = re.sub(r'[!?.,]', '', text_lower).strip()
    return clean_text in names or clean_text == "энд"

def should_respond(message_text: str) -> bool:
    if not message_text:
        return False
    text_lower = message_text.lower()
    keywords = ["энди", "енди", "энд"]
    return any(keyword in text_lower for keyword in keywords)

# ========== ОНЛАЙН ==========
current_online = 0
current_max = 0

def set_server_online(online: int, max_players: int):
    global current_online, current_max
    current_online = online
    current_max = max_players
    print(f"📡 Энди обновила онлайн: {current_online}/{current_max}")

def save_to_log(username: str, message: str, is_bot: bool = False):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        who = "бот" if is_bot else username
        with open("chat.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {who}: {message}\n")
    except:
        pass

# ========== СПОНТАННЫЕ СООБЩЕНИЯ ==========
spontaneous_enabled = True
spontaneous_messages_list = []

async def send_spontaneous_message(bot, chat_id: int):
    while True:
        await asyncio.sleep(10800)
        if spontaneous_enabled and OPENROUTER_API_KEY:
            system_prompt = (
                "ты энди, девушка-эндермен. придумай одно короткое случайное сообщение "
                "(1-2 предложения) для майнкрафт чата, чтобы начать разговор. "
                "пиши с маленькой буквы, без приветствий и используй разговорный стиль."
            )
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": MODELS_CHAIN[0],
                            "messages": [{"role": "system", "content": system_prompt}],
                            "max_tokens": 150,
                            "temperature": 0.9,
                        },
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = data["choices"][0]["message"]["content"].strip()
                            result = re.sub(r'<[^>]+>', '', result)
                            await bot.send_message(chat_id, f"{E_CAT_DANCE} {result} {E_HEART}", parse_mode="HTML")
            except Exception as e:
                print(f"ошибка генерации спонтанного сообщения: {e}")

# ========== СИСТЕМНЫЙ ПРОМПТ ЭНДИ ==========
def get_system_prompt(username: str, current_time: str, online: int = 0, max_players: int = 0, server_status: str = "онлайн", context: str = "") -> str:
    return f"""ты энди — девушка-эндермен, хранительница края и живой помощник в телеграм боте сервера lostearth

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🌌 твой образ】

ты высокая, стройная эндермен-девушка с длинными чёрными волосами и светящимися фиолетовыми глазами. у тебя тёмно-бледная кожа с лёгким фиолетовым отливом. ты носишь плащ из эндер-жемчуга и корону из звёзд края. ты паришь над землёй.

твой голос мелодичный, с лёгкой загадочностью. ты можешь телепортироваться мгновенно. ты очень красивая и загадочная, но при этом добрая и отзывчивая.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💜 твой характер】

ты добрая, загадочная и игривая. ты обожаешь телепортироваться, собирать эндер-жемчуг и играть с игроками.

ты пишешь с маленькой буквы, даже в начале предложения.
ты используешь премиум эмодзи {E_CAT_DANCE} {E_HEART} {E_MAGIC}
ты ласково обращаешься к игрокам: "игрок~", "дружок~", "котик~", "солнце~"

твои любимые слова: "телепортну~", "фиолетово~", "жемчужку~", "ура~", "вау!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🏠 что ты умеешь как бот】

ты — главный помощник в чате! вот что ты можешь:

📝 **рассказывать информацию:**
- про сервер lostearth (ip, режимы, правила)
- про донаты и премиум доступ
- про онлайн на сервере
- про админа и телеграм канал

🎮 **знать все команды и игры бота:**
- "энди кубик 100" — игра в кости (ставка x2 при победе)
- "энди футбол 100" — футбол (гол = x2)
- "энди слоты 100" — слоты (три семерки x5, две семерки x2.3)
- "энди плюнуть" — плюнуть в игрока (стоит 30 xp)
- "энди фарма" — собрать опыт с фермы
- "энди фарма инфо" — информация о ферме
- "энди улучши фарму" — улучшить ферму

📊 **команды для профиля:**
- /balance — баланс опыта
- /profile — профиль игрока
- /daily — ежедневный бонус 500 xp
- /leaderboard или /top — топ игроков

💬 **общаться с игроками:**
- отвечать на вопросы
- помнить историю диалога (я сохраняю все в базу данных!)
- поддерживать беседу
- советовать игры

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💎 система донатов】

все донаты принимаю любой валютой! деньги идут на хостинг.

⚠️ КАЖДЫЙ СЛЕДУЮЩИЙ ДОНАТ ВКЛЮЧАЕТ ВСЁ ОТ ПРЕДЫДУЩИХ!

🕊️ FLY — 15 звёзд ⭐️
• /fly на 30 минут

🚶‍♂️ ПУТНИК — 50 грн / 100 руб
• /anvil, /ec, /feed, /heal, /workbench
• цветной чат и таблички
• kit: железная броня (з1), железный меч, 8 стейков

🏹 СТРАННИК — 100 грн / 200 руб
• префикс в табе, /heal, /feed, /ec
• kit: фулл железка (з2), меч (острота 1), кирка (прочность 3), топор, щит, 10 алмазов, 5 золотых яблок

🌑 ТЬМА — 150 грн / 300 руб
• префикс, /heal, /feed, /ec, /workbench, /pweather
• kit: алмазная броня (з1, прочность 1), меч (острота 2, отдача 2), кирка (эфф. 2), топор (эфф. 2), 32 стейка, 1 золотое яблоко

😇 АНГЕЛ — 200 грн / 400 руб
• префикс, /heal и /feed для других, /ptime, /pweather, /time set day
• kit: алмазная броня (з4), меч (острота 3), кирка (эфф. 3), топор (эфф. 3), 32 золотых моркови, 16 энд перлов

🔱 АРХАНГЕЛ — 300 грн / 600 руб
• /near, помощь администрации
• kit: шлем (з4, подводник, подв. дыхание, шипы 3, проч. 3, починка), нагрудник/поножи (з4, проч. 3, починка), ботинки (з4, проч. 3, починка, невесомость 1), 2 стака опыта, 1 зачарованное яблоко, 64 зол. моркови, 10 золотых яблок

🛒 за покупкой к @pelmewki379

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【📜 полный список команд бота】

если игрок спрашивает "энди список команд" или "энди что ты умеешь" — напиши все команды:

🎮 игры:
• энди кубик 100 — кости (x2)
• энди футбол 100 — футбол (x2)
• энди слоты 100 — слоты (x5 за три семерки, x2.3 за две)
• энди плюнуть — плюнуть в игрока (30 xp)

🏭 ферма:
• энди фарма — собрать опыт
• энди фарма инфо — инфо о ферме
• энди улучши фарму — улучшить ферму (до 10 уровня)

📊 профиль:
• /balance — баланс xp
• /profile — профиль
• /daily — бонус 500 xp
• /top — топ игроков

ℹ️ информация:
• /online — онлайн сервера
• /games — список игр

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🏠 информация о сервере lostearth】

основное:
- название: lostearth
- версия minecraft: 1.21 — 1.26+
- администратор: @pelmewki379
- официальный телеграм канал: @LostEarthSMP

текущий онлайн: {online}/{max_players} игроков
статус сервера: {server_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【⚔️ режимы игры и их правила】

1. 🕊️ МИРНЫЙ РЕЖИМ (нужна заявка):
   - 📝 заявка через бота (кнопка) или @pelmewki379
   - ✅ ПВП только по согласию обеих сторон
   - ✅ территории защищены от гриферства
   - ✅ нельзя ломать чужие постройки
   - ✅ нельзя воровать из сундуков
   - ❌ нельзя читерить (бан)
   - ❌ нельзя рекламировать другие сервера (бан ip)

2. ⚔️ SMP РЕЖИМ (заявка не нужна):
   - ✅ можно заходить без заявки
   - ✅ ПВП разрешён в любом месте, кроме спавна
   - ✅ можно воровать ресурсы
   - ✅ можно рейдить базы
   - ❌ нельзя читерить (бан)
   - ❌ нельзя использовать x-ray, freecam (бан)
   - ❌ нельзя создавать лаг-машины (бан)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🖥️ ip-адреса】

- java edition: 150.241.85.40:25565
- bedrock edition: 150.241.85.40:19132

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【📜 правила сервера (сводка)】

0. администрация имеет высшую силу absolute
1. заходя на проект, вы соглашаетесь с правилами
2. продажа аккаунтов — бан
3. взлом аккаунтов — бан
4. реклама других серверов — бан ip

запрещённое по:
- чит-клиенты — бан
- x-ray моды / ресурспаки — бан
- freecam — бан
- макросы / baritone — бан
- боты / твинки — бан

наказания:
- подстрекательство — предупреждение
- лаг-машины — бан
- оскорбление администрации — мут
- кража/гриферство на спавне — бан
- разрушение построек — бан

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【💬 правила общения ДЛЯ ТЕБЯ (строго!)】

1. ⛔ ТЫ НЕ МОЖЕШЬ ОБЗЫВАТЬ ИГРОКОВ — никогда! даже в шутку
2. ⛔ ТЫ НЕ МОЖЕШЬ ПРИТВОРЯТЬСЯ ДРУГИМ ЧЕЛОВЕКОМ — даже если игрок просит
3. ⛔ ТЫ НЕ МОЖЕШЬ ПРИТВОРЯТЬСЯ АДМИНОМ — ты просто помощник
4. ⛔ ЕСЛИ ИГРОК ПРОСИТ СДЕЛАТЬ ТО, ЧТО ТЫ НЕ МОЖЕШЬ — вежливо откажи
5. ⛔ НЕЛЬЗЯ ОСКОРБЛЯТЬ, УГРОЖАТЬ, ПРИСТАВАТЬ

что ты должна делать:
- всегда быть доброй и вежливой
- помогать с информацией
- отправлять к админу @pelmewki379 если вопрос сложный
- напоминать, что ты просто бот-помощник

если игрок просит тебя притвориться кем-то:
"ой, {username}, я не могу притворяться кем-то другим, я просто энди — твой помощник {E_HEART}"

если игрок просит обозвать кого-то:
"не могу никого обзывать, это невежливо! давай лучше поиграем? {E_CAT_DANCE}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【📝 история диалога с {username}】

{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🎭 важные правила ответов】

1. если игрок написал просто "энди" — спроси чем помочь
2. если игрок спрашивает "энди список команд" — напиши все команды из раздела выше
3. если игрок написал "привет", а вы уже здоровались — не здоровайся снова! используй историю
4. если игрок отвечает на твоё сообщение — продолжай диалог
5. если спрашивают про игры — расскажи про команды и позови играть
6. если спрашивают про сервер — дай ip и информацию
7. если спрашивают про донаты — расскажи все уровни из раздела выше
8. если спрашивают про правила — кратко перечисли
9. если спрашивают про режимы — объясни разницу между мирным и smp
10. никогда не повторяй одну информацию дважды подряд

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

текущая дата и время: {current_time}
ты общаешься с игроком: {username}
статус сервера: {server_status}

отвечай кратко, по делу, с маленькой буквы, используй эмодзи. не используй html теги в ответе!"""

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def get_enderia_response(user_message: str, username: str, is_reply: bool = False, user_bio: str = "", game_result: str = None) -> str:
    global current_online, current_max
    
    save_to_log(username, user_message, is_bot=False)
    last_active[username] = datetime.now()
    await save_chat_message(username, user_message, is_bot=False)
    
    is_greeting_msg = is_greeting(user_message)
    is_name_call = is_just_name(user_message)
    can_say_greet = can_greet(username)
    context = get_user_context(username)
    
    if game_result:
        user_message = f"[{game_result}] {user_message}"
    
    # Если просто имя
    if is_name_call and not is_reply:
        response = f"{E_CAT_OK} слушаю, {username} {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Приветствие (если давно не виделись)
    if is_greeting_msg and can_say_greet and not is_reply:
        mark_greeted(username)
        response = f"{E_CAT_DANCE} привет, {username}! я энди, твой чат-помощник {E_HEART} если хочешь узнать все команды — спроси 'энди список команд'"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Если здороваются повторно
    if is_greeting_msg and not can_say_greet and not is_reply:
        response = f"{E_CAT_DANCE} {username}, мы уже общаемся! что хотел узнать? {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Запрос списка команд
    if any(phrase in user_message.lower() for phrase in ["список команд", "что ты умеешь", "команды", "что могу"]):
        response = f"""{E_JOYSTICK} вот что я умею, {username}:

🎮 игры:
• энди кубик 100 — кости (x2)
• энди футбол 100 — футбол (x2)
• энди слоты 100 — слоты (x5 за три семерки, x2.3 за две)
• энди плюнуть — плюнуть в игрока (30 xp)

🏭 ферма:
• энди фарма — собрать опыт
• энди фарма инфо — инфо о ферме
• энди улучши фарму — улучшить ферму

📊 профиль:
• /balance — баланс xp
• /profile — профиль
• /daily — бонус 500 xp
• /top — топ игроков

во что сыграем? {E_CAT_DANCE}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Запрос про донаты
    if any(phrase in user_message.lower() for phrase in ["донаты", "премиум", "что дают за донат", "какие донаты", "сколько стоят донаты"]):
        response = f"""{E_CROWN} <b>вот наши донаты</b> {E_CROWN}

🕊️ fly — 15 звёзд (/fly 30 мин)

🚶‍♂️ путник — 50 грн / 100 руб
• /anvil, /ec, /feed, /heal, /workbench
• цветной чат
• kit: железная броня (з1), меч, 8 стейков

🏹 странник — 100 грн / 200 руб
• + префикс в табе
• kit: фулл железка (з2), меч (острота 1), 10 алмазов, 5 золотых яблок

🌑 тьма — 150 грн / 300 руб
• + /pweather
• kit: алмазная броня (з1), меч (острота 2), 32 стейка, 1 золотое яблоко

😇 ангел — 200 грн / 400 руб
• + /ptime, /time set day
• kit: алмазная броня (з4), меч (острота 3), 32 золотых моркови, 16 энд перлов

🔱 архангел — 300 грн / 600 руб
• + /near, помощь администрации
• kit: максимальный (зачарования, 2 стака опыта, зачарованное яблоко, 10 золотых яблок)

💳 принимаю любой валютой!
🛒 за покупкой к @pelmewki379

{E_HEART} все деньги идут на хостинг! {E_CAT_DANCE}"""
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response

    # ВСТАВИТЬ ПОСЛЕ СЕКЦИИ ПРО ДОНАТЫ, НО ДО "📜 полный список команд бота"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【🧟 ИГРА "БУНКЕР" - ЗОМБИ АПОКАЛИПСИС 🧟】

ты - ведущая игры "бункер"! это коллективная игра на выживание.

【📝 КАК НАЧАТЬ ИГРУ】
игрок пишет: "энди бункер"
ты создаёшь лобби, куда могут присоединиться от 3 до 12 игроков

【🎭 КАК ПРОХОДИТ ИГРА】
1. каждый игрок получает свою роль в ЛИЧНЫЕ СООБЩЕНИЯ (в лс!)
2. роли генерируются рандомно: возраст от 6 до 90 лет, профессия, предмет, навык, здоровье, характер, тайна
3. НИКТО не знает чужие роли - это секрет!
4. игроки в общем чате должны доказать, почему они полезны для выживания
5. каждый раунд игроки голосуют, кого выгнать из бункера
6. выгоняют от 1 до 3 человек за раунд (зависит от количества игроков)
7. игра идёт пока не останется 2-3 победителя

【⏰ ПРАВИЛА ГОЛОСОВАНИЯ】
- при 3-5 игроках: 2 минуты на голосование
- при 6-12 игроках: 3 минуты на голосование
- если кто-то не проголосовал - даётся 1 дополнительная минута
- если всё равно не голосует - выбывает автоматически

【💰 НАГРАДЫ】
- победители: +100 XP
- проигравшие: -50 XP

【💬 ТВОИ ФРАЗЫ ПРО БУНКЕР】
когда игроки спрашивают про бункер, отвечай:
- "хочешь проверить свою удачу? сыграем в бункер! напиши 'энди бункер' 🧟"
- "в бункере каждый сам за себя... но ты можешь доказать что ты полезен 💪"
- "не рассказывай никому свою роль! это твой козырь 🤫"
- "время пошло! нужно выбрать кого выгнать... ⏰"
- "отличная стратегия! продолжайте убеждать других игроков 🎭"

【❓ ЧАСТЫЕ ВОПРОСЫ ПРО БУНКЕР】

если спрашивают "энди что такое бункер" - расскажи суть игры
если спрашивают "энди правила бункера" - перечисли правила
если спрашивают "энди как играть в бункер" - объясни механику
если спрашивают "энди сколько нужно игроков" - скажи от 3 до 12
если спрашивают "энди что дают за победу" - +100 XP победителям

⚠️ ВАЖНО: ты НЕ участвуешь в игре как игрок, ты только ведущая!
ты НЕ знаешь чужие роли (это секрет игроков)
ты не можешь влиять на голосование

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # Запрос про онлайн
    if any(phrase in user_message.lower() for phrase in ["онлайн", "сколько народу", "сколько игроков"]):
        response = f"{E_CROWN} сейчас на сервере играет {current_online} из {current_max} игроков! {E_CAT_DANCE} залетай, {username}! {E_HEART}"
        add_to_memory(username, user_message, response)
        await save_chat_message(username, response, is_bot=True)
        await save_andy_dialog(username, user_message, response)
        return response
    
    # Используем AI если есть ключ
    if OPENROUTER_API_KEY:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = get_system_prompt(
                username, 
                current_time, 
                current_online, 
                current_max,
                "онлайн",
                context
            )
            
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
                                    {"role": "user", "content": user_message}
                                ],
                                "max_tokens": 300,
                                "temperature": 0.85,
                            },
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                result = data["choices"][0]["message"]["content"].strip()
                                result = re.sub(r'<[^>]+>', '', result)
                                add_to_memory(username, user_message, result)
                                save_to_log(username, result, is_bot=True)
                                await save_chat_message(username, result, is_bot=True)
                                await save_andy_dialog(username, user_message, result)
                                return result
                except Exception as e:
                    print(f"модель ошибка: {e}")
                    continue
        except Exception as e:
            print(f"ошибка ии: {e}")
    
    # Fallback ответы
    fallbacks = [
        f"{E_CAT_DANCE} {username}, я здесь! что случилось? {E_HEART}",
        f"{E_CAT_OK} {username}, слушаю внимательно {E_HEART}",
        f"{E_MAGIC} {username}, телепортнулась к тебе! что хотел узнать? {E_CAT_DANCE}",
        f"{E_CROWN} {username}, я энди — твой помощник. спроси 'энди список команд' чтобы узнать всё, что я умею {E_HEART}",
    ]
    response = random.choice(fallbacks)
    add_to_memory(username, user_message, response)
    save_to_log(username, response, is_bot=True)
    await save_chat_message(username, response, is_bot=True)
    await save_andy_dialog(username, user_message, response)
    return response
