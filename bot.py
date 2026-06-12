import asyncio
import os
import socket
import struct
import json
from datetime import datetime
from threading import Thread

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from flask import Flask

from enderia import get_enderia_response, should_respond

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("BOT_TOKEN not found")

app = Flask(__name__)

@app.route("/")
def health_check():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

BUTTON_EMOJI = {
    "door": "5873147866364514353",
    "note": "5870930744116776638",
    "rabbit_fly": "5217576088506505749",
    "cat_dance": "5359444458930718519",
    "cat_ok": "5269476765369144234",
    "check": "5870633910337015697",
    "back": "5875082500023258804",
    "joystick": "5870717606364713020",
    "crown": "5807868868886009920",
    "house": "5873147866364514353",
    "start": "5870921127685001066",
}

def button_emoji(emoji_id, fallback=""):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

SERVER = {
    "name": "LostEarth",
    "mode": "Mirny rezhim po zayavkam",
    "java_ip": "150.241.85.40",
    "java_port": 25565,
    "java_versions": "1.21 - 1.26",
    "bedrock_ip": "150.241.85.40",
    "bedrock_port": 19132,
}

BASE_URL = "https://lostearthbot-production.up.railway.app"
RULES_URL = f"{BASE_URL}/"
APPLY_URL = f"{BASE_URL}/apply"

online_cache = {}
last_update = {}

async def get_java_status(ip, port=25565):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))
        
        handshake = bytearray()
        handshake += b'\x00'
        handshake += b'\x04\x00\x00\x00'
        host_bytes = ip.encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', port)
        handshake += b'\x01'
        
        value = len(handshake)
        while True:
            if value & ~0x7F == 0:
                sock.send(bytes([value]))
                break
            sock.send(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        
        sock.send(handshake)
        sock.send(b'\x00\x00')
        
        result = 0
        shift = 0
        while True:
            byte = sock.recv(1)[0]
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                length = result
                break
        
        data = b''
        while len(data) < length:
            data += sock.recv(1024)
        sock.close()
        
        data = data[1:]
        json_data = json.loads(data.decode('utf-8'))
        players = json_data.get("players", {})
        return players.get("online", 0), players.get("max", 0)
    except:
        return 0, 0

async def get_server_online():
    now = datetime.now().timestamp()
    if "online" in last_update and now - last_update["online"] < 30:
        return online_cache.get("online", 0), online_cache.get("max", 0)
    online, max_players = await get_java_status(SERVER["java_ip"], SERVER["java_port"])
    online_cache["online"] = online
    online_cache["max"] = max_players
    last_update["online"] = now
    return online, max_players

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="IP I ONLINE", callback_data="menu_ip", icon_custom_emoji_id=BUTTON_EMOJI["door"])],
        [InlineKeyboardButton(text="PRAVILA", web_app=WebAppInfo(url=RULES_URL), icon_custom_emoji_id=BUTTON_EMOJI["note"]),
         InlineKeyboardButton(text="ZAYAVKA", web_app=WebAppInfo(url=APPLY_URL), icon_custom_emoji_id=BUTTON_EMOJI["rabbit_fly"])],
        [InlineKeyboardButton(text="PREMIUM", callback_data="menu_premium", icon_custom_emoji_id=BUTTON_EMOJI["cat_dance"]),
         InlineKeyboardButton(text="ENDERIA", callback_data="menu_enderia", icon_custom_emoji_id=BUTTON_EMOJI["cat_ok"])]
    ])

def get_ip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="OBNOVIT", callback_data="refresh_online", icon_custom_emoji_id=BUTTON_EMOJI["check"])],
        [InlineKeyboardButton(text="NAZAD", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = (button_emoji(BUTTON_EMOJI["start"], " ") + 
            " Dobro pozhalovat na " + SERVER["name"] + "\n\n" +
            button_emoji(BUTTON_EMOJI["house"], " ") + " " + SERVER["mode"] + "\n\n" +
            button_emoji(BUTTON_EMOJI["cat_ok"], " ") + " Ya Enderiya - napishi moyo imya, i ya otvechu")
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("online"))
async def cmd_online(message: Message):
    online, max_players = await get_server_online()
    text = button_emoji(BUTTON_EMOJI["joystick"], " ") + " Online: " + str(online) + "/" + str(max_players)
    await message.answer(text, parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    username = message.from_user.first_name or "Igrok"
    
    if should_respond(message.text):
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        online, _ = await get_server_online()
        response = await get_enderia_response(message.from_user.id, message.chat.id, message.text, username, online)
        
        if response:
            await message.reply(response, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text("Glavnoe menu", parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_ip")
async def menu_ip(callback: CallbackQuery):
    online, max_players = await get_server_online()
    status = "ONLINE" if online > 0 else "OFFLINE"
    text = (button_emoji(BUTTON_EMOJI["crown"], " ") + " LOSTEARTH | " + status + "\n\n" +
            "JAVA: " + SERVER["java_ip"] + ":" + str(SERVER["java_port"]) + "\n" +
            "Online: " + str(online) + "/" + str(max_players) + "\n" +
            "BEDROCK: " + SERVER["bedrock_ip"] + ":" + str(SERVER["bedrock_port"]) + "\n\n" +
            button_emoji(BUTTON_EMOJI["rabbit_fly"], " ") + " Priyatnoy igry")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "refresh_online")
async def refresh_online(callback: CallbackQuery):
    online_cache.clear()
    last_update.clear()
    online, max_players = await get_server_online()
    status = "ONLINE" if online > 0 else "OFFLINE"
    text = (button_emoji(BUTTON_EMOJI["crown"], " ") + " LOSTEARTH | " + status + "\n\n" +
            "JAVA: " + SERVER["java_ip"] + ":" + str(SERVER["java_port"]) + "\n" +
            "Online: " + str(online) + "/" + str(max_players) + "\n" +
            "BEDROCK: " + SERVER["bedrock_ip"] + ":" + str(SERVER["bedrock_port"]) + "\n\n" +
            button_emoji(BUTTON_EMOJI["rabbit_fly"], " ") + " Priyatnoy igry")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_ip_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_premium")
async def menu_premium(callback: CallbackQuery):
    text = (button_emoji(BUTTON_EMOJI["cat_dance"], " ") + " PREMIUM DOSTUP\n\n" +
            "Druid - 50 rub\n" +
            "Orakul - 100 rub\n" +
            "Monarh - 200 rub\n" +
            "Heruvim - 300 rub\n" +
            "Arhont - 400 rub\n" +
            "Serafim - 600 rub\n\n" +
            "Po voprosam: @pelmewki379")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="NAZAD", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_enderia")
async def menu_enderia(callback: CallbackQuery):
    text = (button_emoji(BUTTON_EMOJI["cat_dance"], " ") + " Enderiya\n\n" +
            button_emoji(BUTTON_EMOJI["cat_ok"], " ") + " Ya devushka-endermen iz LostEarth!\n\n" +
            "Napishi: Ender, Enderiya, Endi - ya otvechu")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="NAZAD", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("=" * 50)
    print("BOT STARTED")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
