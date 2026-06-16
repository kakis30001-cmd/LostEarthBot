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
    
    # Скрытые характеристики (изначально неизвестны другим)
    hidden_profession: str = None
    hidden_health: str = None
    
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
    WAITING = "waiting"                # Ожидание игроков
    CHARACTERS_GENERATED = "characters_generated"  # Роли созданы
    REVEALING = "revealing"            # Игроки раскрывают информацию
    VOTING = "voting"                  # Голосование
    FINISHED = "finished"              # Игра окончена

@dataclass
class BunkerPlayer:
    user_id: int
    username: str
    character: Optional[BunkerCharacter] = None
    is_alive: bool = True
    vote_count: int = 0
    has_voted: bool = False
    revealed: List[str] = None  # Что раскрыл игрок
    cards: List[str] = None     # Рандомные карточки
    has_revealed_this_round: bool = False  # Уже раскрывал в этом раунде

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
        self.reveal_messages: Dict[int, int] = {}  # user_id -> message_id
        self.game_started = False
        
    def generate_random_character(self) -> BunkerCharacter:
        """Генерирует персонажа"""
        age = random.randint(16, 65)
        genders = ["мужчина", "женщина"]
        gender = random.choice(genders)
        
        professions = [
            "врач", "военный", "инженер", "повар", "фермер", "механик",
            "электрик", "строитель", "охотник", "рыбак", "химик", "программист",
            "учитель", "сантехник", "пожарный", "полицейский", "адвокат"
        ]
        profession = random.choice(professions)
        
        hobbies = [
            "чтение книг", "игра на гитаре", "рисование", "садоводство",
            "рыбалка", "охота", "готовка", "медитация", "спорт"
        ]
        hobby = random.choice(hobbies)
        
        baggage = [
            "рюкзак с едой", "аптечка", "набор инструментов", "оружие",
            "книги", "семена", "вода", "тёплая одежда"
        ]
        baggage = random.choice(baggage)
        
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
        
        healths = [
            "отличное", "хорошее", "среднее", "слабое", "хронические проблемы"
        ]
        health = random.choice(healths)
        
        mental_states = [
            "стабильная", "тревожная", "депрессивная", "параноидальная", "агрессивная"
        ]
        mental_state = random.choice(mental_states)
        
        return BunkerCharacter(
            age=age, gender=gender, profession=profession,
            hobby=hobby, baggage=baggage, skill=skill,
            fact=fact, good_at=good_at, health=health,
            mental_state=mental_state
        )
    
    def generate_random_cards(self) -> List[str]:
        """Генерирует 1 случайную карточку"""
        cards = [
            "🔄 заменить профессию", "🔄 заменить здоровье", "🔄 заменить умение",
            "🔄 заменить психику", "🔄 заменить хобби", "🔄 заменить багаж"
        ]
        return [random.choice(cards)]
    
    async def generate_all_characters(self):
        """Отправляет роли в ЛС каждому игроку"""
        for player in self.players.values():
            player.character = self.generate_random_character()
            player.revealed = []
            player.cards = self.generate_random_cards()
            
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎮 ВЕРНУТЬСЯ В ЧАТ", url=f"https://t.me/lostearth_bot?start=group")]
                ])
                
                await self.bot.send_message(
                    player.user_id,
                    player.character.get_full_description() + f"\n\n🎴 <b>твоя карточка:</b> {player.cards[0]}",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as e:
                print(f"Не удалось отправить в ЛС {player.username}: {e}")
        
        self.state = GameState.CHARACTERS_GENERATED
        self.game_started = True
    
    async def start_reveal_phase(self):
        """Начинает фазу раскрытия информации"""
        self.state = GameState.REVEALING
        
        # Создаём кнопки для раскрытия
        for player in self.players.values():
            if not player.is_alive:
                continue
            
            keyboard = self.get_reveal_keyboard(player)
            msg = await self.bot.send_message(
                player.user_id,
                f"{E_MAGIC} <b>выбери что раскрыть о себе!</b>\n\n"
                f"<i>другие увидят только то, что ты выберешь</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            self.reveal_messages[player.user_id] = msg.message_id
        
        # Запускаем таймер на 90 секунд
        asyncio.create_task(self.reveal_timer())
    
    def get_reveal_keyboard(self, player: BunkerPlayer) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру для выбора раскрытия (только 1 за раунд)"""
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
    
    # Если игрок уже раскрыл что-то в этом раунде - блокируем выбор
    if player.has_revealed_this_round:
        # Показываем что уже раскрыто
        for label, key in options:
            if key in player.revealed:
                buttons.append([InlineKeyboardButton(f"✅ {label}", callback_data=f"reveal_{key}")])
            else:
                buttons.append([InlineKeyboardButton(f"🔒 {label}", callback_data=f"reveal_locked")])
        buttons.append([InlineKeyboardButton("✅ ГОТОВО", callback_data="reveal_done")])
    else:
        # Можно выбрать только 1
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
                f"{E_CAT_SURPRISED} <b>ВРЕМЯ НА РАСКРЫТИЕ ЗАКОНЧИЛОСЬ!</b>",
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
        
        # Запускаем таймер голосования
        asyncio.create_task(self.voting_timer())
    
    async def send_vote_menu(self, voter: BunkerPlayer):
        """Отправляет меню голосования в ЛС"""
        alive_others = [p for p in self.get_alive_players() if p.user_id != voter.user_id]
        
        if not alive_others:
            await self.bot.send_message(voter.user_id, "❌ некого выгонять!", parse_mode="HTML")
            return
        
        buttons = []
        for target in alive_others:
            info = target.character.get_public_info(target.revealed)
            label = f"❌ {target.username}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"vote_{target.user_id}")])
        
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
            # Игра окончена
            await self.finish_game()
        else:
            await self.bot.send_message(self.chat_id, result_text, parse_mode="HTML")
            self.current_round += 1
            await self.start_reveal_phase()
    
    async def finish_game(self):
        """Завершает игру с концовкой"""
        survivors = self.get_alive_players()
        
        # Генерируем концовку
        ending = await self.generate_ending(survivors)
        
        result_text = f"{E_CROWN} 🧟 <b>ИГРА ЗАКОНЧЕНА!</b> 🧟 {E_CROWN}\n\n"
        result_text += f"{ending}\n\n"
        result_text += f"{E_CROWN} <b>ПОБЕДИТЕЛИ:</b> {E_CROWN}\n"
        
        for player in survivors:
            await update_xp(player.username, 200)
            result_text += f"✨ {player.username} +200 XP!\n"
        
        await self.bot.send_message(self.chat_id, result_text, parse_mode="HTML")
        self.state = GameState.FINISHED
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
        
        # Добавляем общую концовку
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
