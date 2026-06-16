import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from database import update_xp
from enderia import E_CROWN, E_MAGIC, E_HOUSE, E_HEART, E_CAT_SURPRISED, E_CAT_DANCE, E_NOTE


@dataclass
class BunkerCharacter:
    """Полный персонаж игрока"""
    age: int
    gender: str
    profession: str
    hobby: str
    baggage: str
    skill: str
    fact: str
    good_at: str
    health: str
    mental_state: str
    
    def get_full_description(self) -> str:
        """Полное описание для ЛС"""
        return f"""
🎭 <b>ТВОЙ ПЕРСОНАЖ В БУНКЕРЕ</b> 🎭

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>возраст:</b> {self.age} лет
⚥ <b>пол:</b> {self.gender}
💼 <b>профессия:</b> {self.profession}
🎯 <b>хобби:</b> {self.hobby}
🎒 <b>багаж:</b> {self.baggage}
⭐ <b>умение:</b> {self.skill}
📌 <b>факт о тебе:</b> {self.fact}
🏆 <b>в чём ты хорош:</b> {self.good_at}
🏥 <b>здоровье:</b> {self.health}
🧠 <b>психика:</b> {self.mental_state}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ЭТО ТОЛЬКО ДЛЯ ТЕБЯ!</b>
💡 <i>ты будешь выбирать, что раскрыть другим</i>
"""
    
    def get_public_info(self, revealed: List[str]) -> str:
        """Публичная информация (только то, что раскрыто)"""
        info = []
        if "profession" in revealed:
            info.append(f"💼 профессия: {self.profession}")
        if "hobby" in revealed:
            info.append(f"🎯 хобби: {self.hobby}")
        if "baggage" in revealed:
            info.append(f"🎒 багаж: {self.baggage}")
        if "skill" in revealed:
            info.append(f"⭐ умение: {self.skill}")
        if "fact" in revealed:
            info.append(f"📌 факт: {self.fact}")
        if "good_at" in revealed:
            info.append(f"🏆 хорош в: {self.good_at}")
        if "health" in revealed:
            info.append(f"🏥 здоровье: {self.health}")
        if "mental_state" in revealed:
            info.append(f"🧠 психика: {self.mental_state}")
        
        if not info:
            return "❌ ничего не раскрыто"
        return "\n".join(info)


class GameState(Enum):
    WAITING = "waiting"
    CHARACTERS_GENERATED = "characters_generated"
    REVEALING = "revealing"
    VOTING = "voting"
    FINISHED = "finished"


@dataclass
class BunkerPlayer:
    user_id: int
    username: str
    character: Optional[BunkerCharacter] = None
    is_alive: bool = True
    vote_count: int = 0
    has_voted: bool = False
    revealed: List[str] = None
    cards: List[str] = None
    has_revealed_this_round: bool = False


class BunkerGame:
    def __init__(self, chat_id: int, host_id: int, bot):
        self.chat_id = chat_id
        self.host_id = host_id
        self.bot = bot
        self.players: Dict[int, BunkerPlayer] = {}
        self.state = GameState.WAITING
        self.current_round = 0
        self.voting_start_time = None
        self.discussion_start_time = None
        self.lobby_message_id = None
        self.reveal_messages: Dict[int, int] = {}
        self.pinned_message_id = None
        self.game_started = False
        
    def generate_random_character(self) -> BunkerCharacter:
        """Генерирует персонажа со смешным багажом"""
        age = random.randint(16, 65)
        genders = ["мужчина", "женщина"]
        gender = random.choice(genders)
        
        professions = [
            "врач", "военный", "инженер", "повар", "фермер", "механик",
            "электрик", "строитель", "охотник", "рыбак", "химик", "программист",
            "учитель", "сантехник", "пожарный", "полицейский", "адвокат",
            "сексолог", "массажист", "психолог"
        ]
        profession = random.choice(professions)
        
        hobbies = [
            "чтение книг", "игра на гитаре", "рисование", "садоводство",
            "рыбалка", "охота", "готовка", "медитация", "спорт"
        ]
        hobby = random.choice(hobbies)
        
        # Багаж с редкими предметами
        normal_items = [
            "рюкзак с едой", "аптечка", "набор инструментов", "оружие",
            "книги", "семена", "вода", "тёплая одежда", "спальный мешок",
            "фонарик", "верёвка", "котелок", "спички", "компас"
        ]
        rare_items = [
            "резиновая баба (всю ночь не давала уснуть)",
            "дилдо (до сих пор не понял, зачем он тут)",
            "пачка прокладок (пригодились как перевязочный материал)",
            "секс-кукла (заменила подушку)",
            "вибратор (использую как массажёр)",
            "порножурнал (читал инструкции по выживанию)",
            "засушенный член (сувенир из прошлого)"
        ]
        baggage = random.choice(rare_items) if random.random() < 0.15 else random.choice(normal_items)
        
        skills = [
            "отличный стрелок", "умеет делать операции", "готовит из ничего",
            "видит в темноте", "чувствует ложь", "вскрывает замки",
            "знает языки", "быстро бегает"
        ]
        skill = random.choice(skills)
        
        facts = [
            "был в армии", "работал в морге", "жил в лесу 5 лет",
            "победил в соревнованиях", "спас человека", "был в опасной экспедиции"
        ]
        fact = random.choice(facts)
        
        good_at = [
            "в экстремальных ситуациях", "в общении с людьми", "в планировании",
            "в импровизации", "в психологии", "в выживании"
        ]
        good_at = random.choice(good_at)
        
        healths = ["отличное", "хорошее", "среднее", "слабое", "хронические проблемы"]
        health = random.choice(healths)
        
        mental_states = ["стабильная", "тревожная", "депрессивная", "параноидальная", "агрессивная"]
        mental_state = random.choice(mental_states)
        
        return BunkerCharacter(
            age=age, gender=gender, profession=profession,
            hobby=hobby, baggage=baggage, skill=skill,
            fact=fact, good_at=good_at, health=health,
            mental_state=mental_state
        )
    
    def generate_random_cards(self) -> List[str]:
        cards = [
            "🔄 заменить профессию", "🔄 заменить здоровье", "🔄 заменить умение",
            "🔄 заменить психику", "🔄 заменить хобби", "🔄 заменить багаж"
        ]
        return [random.choice(cards)]
    
    async def generate_all_characters(self):
        """Отправляет роли в ЛС каждому игроку с кнопкой перехода в бота"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        for player in self.players.values():
            player.character = self.generate_random_character()
            player.revealed = []
            player.cards = self.generate_random_cards()
            
            # Кнопка для перехода в бота и начала игры
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 ЗАЙТИ В БОТА И НАЧАТЬ", url="https://t.me/lostearth_bot?start=bunker")]
            ])
            
            try:
                await self.bot.send_message(
                    player.user_id,
                    player.character.get_full_description() + f"\n\n🎴 <b>твоя карточка:</b> {player.cards[0]}\n\n👇 <b>нажми на кнопку чтобы перейти в бота и начать игру</b>",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as e:
                print(f"Не удалось отправить в ЛС {player.username}: {e}")
        
        self.state = GameState.CHARACTERS_GENERATED
        self.game_started = True
        
        # Отправляем закреплённое сообщение в чат
        await self.send_pinned_message()
    
    async def send_pinned_message(self):
        """Отправляет закреплённое сообщение с кнопкой перехода в бота"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ПЕРЕЙТИ В БОТА", url="https://t.me/lostearth_bot?start=bunker")]
        ])
        
        msg = await self.bot.send_message(
            self.chat_id,
            f"{E_CROWN} 🧟 <b>ИГРА БУНКЕР НАЧАЛАСЬ!</b> 🧟 {E_CROWN}\n\n"
            f"{E_MAGIC} <b>всем игрокам отправлены роли в ЛС!</b>\n\n"
            f"📌 <b>как играть:</b>\n"
            f"1️⃣ перейди в бота по кнопке ниже\n"
            f"2️⃣ выбери 1 характеристику для раскрытия\n"
            f"3️⃣ жди остальных игроков\n"
            f"4️⃣ после раскрытия всех - голосование\n\n"
            f"<i>в каждом раунде раскрывается 1 новая характеристика!</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        try:
            await self.bot.pin_chat_message(self.chat_id, msg.message_id)
            self.pinned_message_id = msg.message_id
        except Exception as e:
            print(f"Не удалось закрепить сообщение: {e}")
    
    async def start_reveal_phase(self):
        """Начинает фазу раскрытия информации (в боте)"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        self.state = GameState.REVEALING
        
        for player in self.get_alive_players():
            player.has_revealed_this_round = False
        
        alive_players = self.get_alive_players()
        
        # Создаём кнопки для раскрытия в боте
        for player in self.players.values():
            if not player.is_alive:
                continue
            
            keyboard = self.get_reveal_keyboard(player)
            
            await self.bot.send_message(
                player.user_id,
                f"{E_MAGIC} <b>раунд {self.current_round + 1}</b> {E_MAGIC}\n\n"
                f"<b>выбери 1 характеристику для раскрытия:</b>\n\n"
                f"<i>выбери и нажми 'ГОТОВО' чтобы подтвердить</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        asyncio.create_task(self.reveal_timer())
    
    def get_reveal_keyboard(self, player: BunkerPlayer):
        """Создаёт клавиатуру для выбора раскрытия (только 1 за раунд)"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        options = [
            ("💼 профессия", "profession"),
            ("🎯 хобби", "hobby"),
            ("🎒 багаж", "baggage"),
            ("⭐ умение", "skill"),
            ("📌 факт", "fact"),
            ("🏆 хорош в", "good_at"),
            ("🏥 здоровье", "health"),
            ("🧠 психика", "mental_state"),
        ]
        
        if player.has_revealed_this_round:
            for label, key in options:
                if key in player.revealed:
                    buttons.append([InlineKeyboardButton(f"✅ {label}", callback_data=f"reveal_{key}")])
                else:
                    buttons.append([InlineKeyboardButton(f"🔒 {label}", callback_data="reveal_locked")])
            buttons.append([InlineKeyboardButton("✅ ГОТОВО", callback_data="reveal_done")])
        else:
            for label, key in options:
                if key in player.revealed:
                    buttons.append([InlineKeyboardButton(f"✅ {label}", callback_data=f"reveal_{key}")])
                else:
                    buttons.append([InlineKeyboardButton(f"◻️ {label}", callback_data=f"reveal_{key}")])
            buttons.append([InlineKeyboardButton("✅ ГОТОВО", callback_data="reveal_done")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def reveal_timer(self):
        """Таймер 90 секунд на раскрытие"""
        await asyncio.sleep(90)
        
        if self.state == GameState.REVEALING:
            await self.bot.send_message(
                self.chat_id,
                f"{E_CAT_SURPRISED} <b>ВРЕМЯ НА РАСКРЫТИЕ ЗАКОНЧИЛОСЬ!</b>\n\nначинаем голосование!",
                parse_mode="HTML"
            )
            await self.start_voting_phase()
    
    async def start_voting_phase(self):
        """Начинает фазу голосования"""
        self.state = GameState.VOTING
        
        alive_players = self.get_alive_players()
        
        # Показываем в чате информацию о всех игроках
        info_text = f"{E_CROWN} <b>ИНФОРМАЦИЯ О ВЫЖИВШИХ:</b> {E_CROWN}\n\n"
        for player in alive_players:
            info_text += f"👤 <b>{player.username}</b>:\n"
            info_text += player.character.get_public_info(player.revealed)
            info_text += "\n\n"
        
        await self.bot.send_message(self.chat_id, info_text, parse_mode="HTML")
        
        # Отправляем голосование в ЛС каждому игроку
        for player in alive_players:
            await self.send_vote_menu(player)
        
        asyncio.create_task(self.voting_timer())
    
    async def send_vote_menu(self, voter: BunkerPlayer):
        """Отправляет меню голосования в ЛС"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        alive_others = [p for p in self.get_alive_players() if p.user_id != voter.user_id]
        
        if not alive_others:
            await self.bot.send_message(voter.user_id, "❌ некого выгонять!", parse_mode="HTML")
            return
        
        buttons = []
        for target in alive_others:
            buttons.append([InlineKeyboardButton(f"❌ {target.username}", callback_data=f"vote_{target.user_id}")])
        
        buttons.append([InlineKeyboardButton("⏭️ ПРОПУСТИТЬ", callback_data="vote_skip")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await self.bot.send_message(
            voter.user_id,
            f"{E_CROWN} <b>ГОЛОСОВАНИЕ!</b> {E_CROWN}\n\n"
            f"<b>выбери кого выгнать из бункера:</b>\n\n"
            f"<i>внимательно изучи информацию о других</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    async def voting_timer(self):
        """Таймер голосования - 2 минуты"""
        await asyncio.sleep(120)
        
        if self.state == GameState.VOTING:
            await self.finish_voting()
    
    async def finish_voting(self):
        """Завершает голосование"""
        alive_players = self.get_alive_players()
        
        if not alive_players:
            return
        
        alive_players.sort(key=lambda x: x.vote_count, reverse=True)
        to_eliminate = self.get_players_to_eliminate()
        eliminated = alive_players[:to_eliminate]
        
        result_text = f"{E_CAT_DANCE} <b>результаты голосования:</b>\n\n"
        
        for player in eliminated:
            player.is_alive = False
            result_text += f"❌ {player.username} - выгнан из бункера! (голосов: {player.vote_count})\n"
            await update_xp(player.username, -50)
        
        remaining = self.get_alive_players()
        
        if len(remaining) <= 3:
            await self.finish_game()
        else:
            await self.bot.send_message(self.chat_id, result_text, parse_mode="HTML")
            self.current_round += 1
            await self.start_reveal_phase()
    
    async def finish_game(self):
        """Завершает игру с концовкой"""
        survivors = self.get_alive_players()
        
        ending = await self.generate_ending(survivors)
        
        result_text = f"{E_CROWN} 🧟 <b>ИГРА ЗАКОНЧЕНА!</b> 🧟 {E_CROWN}\n\n"
        result_text += f"{ending}\n\n"
        result_text += f"{E_CROWN} <b>ПОБЕДИТЕЛИ:</b> {E_CROWN}\n"
        
        for player in survivors:
            await update_xp(player.username, 200)
            result_text += f"✨ {player.username} +200 XP!\n"
        
        await self.bot.send_message(self.chat_id, result_text, parse_mode="HTML")
        self.state = GameState.FINISHED
        
        from bot import active_bunker_games
        if self.chat_id in active_bunker_games:
            del active_bunker_games[self.chat_id]
    
    async def generate_ending(self, survivors: List[BunkerPlayer]) -> str:
        """Генерирует финальную концовку"""
        endings = []
        
        for player in survivors:
            health = player.character.health
            mental = player.character.mental_state
            
            if health in ["отличное", "хорошее"] and mental in ["стабильная"]:
                endings.append(f"👤 {player.username} - выжил и стал лидером новой общины!")
            elif health in ["слабое", "хронические проблемы"]:
                endings.append(f"👤 {player.username} - выжил, но здоровье подвело...")
            elif mental in ["депрессивная", "параноидальная"]:
                endings.append(f"👤 {player.username} - выжил, но психика сломана...")
            else:
                endings.append(f"👤 {player.username} - выжил, несмотря ни на что!")
        
        random_ending = random.choice([
            "Бункер выстоял! Зомби отступили!",
            "Вы нашли выход из бункера и спаслись!",
            "Сигнал о помощи был принят! Спасение близко!",
            "В бункере началась новая жизнь..."
        ])
        
        return "\n".join(endings) + f"\n\n{random_ending} {E_HEART}"
    
    def get_alive_players(self) -> List[BunkerPlayer]:
        return [p for p in self.players.values() if p.is_alive]
    
    def get_players_to_eliminate(self) -> int:
        alive = len(self.get_alive_players())
        rules = {5: 1, 6: 2, 7: 2, 8: 2, 9: 2, 10: 3}
        return rules.get(alive, 1)
    
    def can_start(self) -> bool:
        return 5 <= len(self.players) <= 10
