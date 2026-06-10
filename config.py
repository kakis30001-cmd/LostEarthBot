import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# ВСЕ ТВОИ НОВЫЕ ЭМОДЗИ (котики, зайцы, аниме)
EMOJI = {
    # Котики
    "cat_rose": "5269347667242162562",      # котик даёт розу
    "cat_surprised": "5269649173946345008", # котик удивлён
    "cat_think": "5267520618219218205",     # котик думает
    "cat_money": "5267058870580191916",     # котик при деньгах
    "cat_angry": "5267380202853408851",     # котик злой
    "cat_down": "5267021749177855750",      # котик палец вниз
    "cat_judge": "5267000000000000000",     # котик судья (добавь свой ID)
    "cat_up": "5269698007724499331",        # котик палец вверх
    "cat_ok": "5269476765369144234",        # котик делает 🤙
    "cat_glasses": "5267088110717544191",   # котик в очках
    "cat_dance": "5359444458930718519",     # котик танцует
    "cat_kiss": "6325462176660195024",      # котик целует
    "cat_laugh": "5276391181679366784",     # котик смеётся
    
    # Зайчики
    "rabbit_tongue": "5217979905626643814", # зайчик язык показывает
    "rabbit_silly": "5217970924850027976",  # глупый зайчик
    "rabbit_smile": "5219869124301199449",  # кролик улыбается
    "rabbit_fly": "5217576088506505749",    # кролик летит на помощь
    
    # Аниме
    "anime_dance": "6325682031741109665",   # аниме тяночка танцует
    
    # Иконки
    "house": "5873147866364514353",         # домик
    "crown": "5807868868886009920",         # корона
    "joystick": "5870717606364713020",      # джойстик
    "note": "5870930744116776638",          # заметка
    "check": "5870633910337015697",         # галочка
    "cross": "5870657884844462243",         # крестик
    "back": "5875082500023258804",          # назад
    "door": "5873147866364514353",          # дверь
    "microphone": "5870831513192369918",    # микрофон
    "start": "5870921127685001066",         # старт
    "magic": "5474144592817318927",         # магия
}

def emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# Сервера
SERVERS = {
    "peaceful": {
        "name": "🌾 Мирный режим",
        "description": "🤝 ПВП только по согласию • 🏠 Территории защищены • 📝 Доступ по заявкам",
        "java_ip": "150.241.85.40",
        "java_port": 25565,
        "bedrock_ip": "150.241.85.40",
        "bedrock_port": 19132,
        "version": "1.21—1.26+",
        "donate_contact": "@pelmewki379"
    },
    "smp": {
        "name": "⚔️ SMP режим",
        "description": "⚔️ PVP разрешён • 🏠 Гриферство запрещено • 🧙 Читы = бан",
        "java_ip": "smp.lostearth.ru",  # замени на свой
        "java_port": 25565,
        "bedrock_ip": "smp.lostearth.ru",  # замени на свой
        "bedrock_port": 19132,
        "version": "1.21—1.26+",
    }
}

HUB_IP = "hub.lostearth.ru"
HUB_PORT = 25565

# Правила (с котиками, зайцами и аниме!)
RULES_PEACEFUL = f"""
{emoji(EMOJI['cat_glasses'], '🐱')} <b>📜 ПРАВИЛА МИРНОГО РЕЖИМА</b> {emoji(EMOJI['cat_glasses'], '🐱')}

{emoji(EMOJI['cat_judge'], '👨‍⚖️')} <b>Общие правила:</b>

0. {emoji(EMOJI['crown'], '👑')} Администрация имеет большую силу, чем правила

1. {emoji(EMOJI['cat_ok'], '🤙')} Заходя на проект, вы соглашаетесь со всеми правилами

2. {emoji(EMOJI['cat_money'], '💰')} Продажа аккаунтов — <b>ЗАПРЕЩЕНА</b> [БАН]

3. {emoji(EMOJI['cat_angry'], '😠')} Взлом аккаунтов — <b>ЗАПРЕЩЁН</b> [БАН]

4. {emoji(EMOJI['cat_surprised'], '😲')} <b>ЗАПРЕЩЁННОЕ ПО</b> [БАН]:
   • Чит-клиенты
   • X-Ray моды и ресурпаки
   • Freecam (свободная камера)
   • Макросы и скрипты (Baritone)
   • Боты/твинки

5. {emoji(EMOJI['rabbit_tongue'], '👅')} Реклама других серверов — [БАН ПО IP]

{emoji(EMOJI['cat_think'], '🤔')} <b>Нарушения:</b>
• {emoji(EMOJI['cross'], '❌')} Подстрекательство — [ПРЕДУПРЕЖДЕНИЕ]
• {emoji(EMOJI['cat_down'], '👇')} Помеха работе модерации — [ПРЕДУПРЕЖДЕНИЕ]
• {emoji(EMOJI['rabbit_silly'], '🤪')} Лаг-машины — [БАН]
• {emoji(EMOJI['cat_angry'], '😤')} Оскорбление администрации — [МУТ]

{emoji(EMOJI['house'], '🏠')} <b>На спавне:</b>
• {emoji(EMOJI['cross'], '❌')} Кража и гриферство — [БАН]
• {emoji(EMOJI['cross'], '❌')} Разрушение домов — [БАН]

{emoji(EMOJI['anime_dance'], '💃')} <i>Играй честно, уважай других!</i>
"""

RULES_SMP = f"""
{emoji(EMOJI['crown'], '⚔️')} <b>ПРАВИЛА SMP РЕЖИМА</b> {emoji(EMOJI['crown'], '⚔️')}

{emoji(EMOJI['cat_money'], '💰')} <b>РАЗРЕШЕНО:</b>
• {emoji(EMOJI['check'], '✅')} PVP в любом месте
• {emoji(EMOJI['check'], '✅')} Воровство ресурсов
• {emoji(EMOJI['check'], '✅')} Рейды на базы
• {emoji(EMOJI['check'], '✅')} Уничтожение построек

{emoji(EMOJI['cat_angry'], '🚫')} <b>ЗАПРЕЩЕНО:</b>
• {emoji(EMOJI['cross'], '❌')} Читы и X-Ray
• {emoji(EMOJI['cross'], '❌')} Лаг-машины
• {emoji(EMOJI['cross'], '❌')} Дюп предметов
• {emoji(EMOJI['cross'], '❌')} Вредительство серверу
• {emoji(EMOJI['cross'], '❌')} Оскорбления в чате

{emoji(EMOJI['rabbit_tongue'], '🐰')} <i>Выживай и побеждай честно!</i>
"""

# ДОНАТЫ / ПРЕМИУМ (мирный режим)
DONATES = {
    "druid": {
        "name": "🌿 Друид",
        "price_hrn": 25,
        "price_rub": 50,
        "emoji": "🌿",
        "features": [
            "Префикс в чате и табе",
            "/anvil - наковальня",
            "/wb - верстак",
            "/ec - эндер-сундук",
            "/kit druid"
        ]
    },
    "oracul": {
        "name": "🔮 Оракул",
        "price_hrn": 50,
        "price_rub": 100,
        "emoji": "🔮",
        "features": [
            "Префикс в чате и табе",
            "2 точки дома",
            "/heal - лечение",
            "/feed - насыщение",
            "/anvil, /ec, /wb",
            "/kit oracul"
        ]
    },
    "monarh": {
        "name": "👑 Монарх",
        "price_hrn": 100,
        "price_rub": 200,
        "emoji": "👑",
        "features": [
            "Восстановление здоровья и сытости себе и другим",
            "Больше домов",
            "/ec, /wb, /anvil",
            "/feed, /heal",
            "/kit monarh",
            "2 точки дома!"
        ]
    },
    "heruvim": {
        "name": "🪽 Херувим",
        "price_hrn": 150,
        "price_rub": 300,
        "emoji": "🪽",
        "features": [
            "Префикс в чате и табе",
            "ПОЛЁТ!",
            "Управление личным временем",
            "Больше домов",
            "/ec, /anvil, /feed",
            "/heal (себе и другим)",
            "/fly - полёт",
            "/ptime <время>",
            "/kit heruvim",
            "2 точки дома!"
        ]
    },
    "arhont": {
        "name": "🏛️ Архонт",
        "price_hrn": 200,
        "price_rub": 400,
        "emoji": "🏛️",
        "features": [
            "Префикс в чате и табе",
            "ПОЛЁТ!",
            "Управление временем",
            "Больше домов",
            "/ec, /anvil, /feed",
            "/heal (себе и другим)",
            "/fly",
            "/ptime",
            "/kit arhont",
            "3 точки дома!"
        ]
    },
    "serafim": {
        "name": "😇 Серафим",
        "price_hrn": 300,
        "price_rub": 600,
        "emoji": "😇",
        "features": [
            "Префикс в чате и табе",
            "ПОЛЁТ!",
            "Управление личным временем",
            "Больше домов",
            "/ec, /anvil, /feed",
            "/heal (себе и другим)",
            "/fly",
            "/ptime",
            "/kit serafim",
            "3 точки дома!"
        ]
    }
}
