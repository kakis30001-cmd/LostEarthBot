# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# ТВОИ ЭМОДЗИ (работают как в примере)
EMOJI = {
    "cat_up": "5269698007724499331",
    "cat_ok": "5269476765369144234",
    "cat_glasses": "5267088110717544191",
    "rabbit_smile": "5219869124301199449",
    "rabbit_fly": "5217576088506505749",
    "anime_dance": "6325682031741109665",
    "cat_kiss": "6325462176660195024",
    "cat_surprised": "5242261773817492813",
    "cat_dance": "5359444458930718519",
    "cat_laugh": "5276391181679366784",
    "house": "5873147866364514353",
    "microphone": "5870831513192369918",
    "notification": "5870886806601338791",
    "start": "5870921127685001066",
    "down": "5872771279337033184",
    "note": "5870930744116776638",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "document": "5875206779196935950",
    "person": "5879770735999717115",
    "back": "5875082500023258804",
    "door": "5873147866364514353",
    "joystick": "5870717606364713020",
}

def emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# Сервер
SERVER = {
    "name": "LostEarth",
    "mode": "Мирный режим по заявкам!",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "java_versions": "1.21—1.26+",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}
