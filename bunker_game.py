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
    """Персонаж игрока"""
    age: int
    gender: str
    profession: str
    item: str
    skill: str
    health: str
    trait: str
    secret: str
    
    def get_description(self) -> str:
        return f"""
🎭 <b>ТВОЙ ПЕРСОНАЖ В БУНКЕРЕ</b> 🎭

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>возраст:</b> {self.age} лет
⚥ <b>пол:</b> {self.gender}
💼 <b>профессия:</b> {self.profession}
🎒 <b>предмет:</b> {self.item}
⭐ <b>навык:</b> {self.skill}
🏥 <b>здоровье:</b> {self.health}
📊 <b>характер:</b> {self.trait}
🔮 <b>тайна:</b> {self.secret}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>НИКОМУ НЕ РАССКАЗЫВАЙ СВОЮ РОЛЬ!</b>
"""


class GameState(Enum):
    WAITING = "waiting"
    CHARACTERS_GENERATED = "characters_generated"
    DISCUSSION = "discussion"
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
        
    def generate_random_character(self) -> BunkerCharacter:
        age = random.randint(6, 90)
        genders = ["мужчина", "женщина", "небинарная персона"]
        gender = random.choice(genders)
        
        professions = [
            "врач-хирург", "военный снайпер", "инженер", "шеф-повар",
            "фермер", "механик", "электрик", "строитель", "охотник",
            "рыбак", "химик", "программист", "учитель", "дальнобойщик",
            "сантехник", "пожарный", "полицейский", "адвокат", "бизнесмен"
        ]
        profession = random.choice(professions)
        
        items = [
            "зажигалка", "молоток", "аптечка", "тушёнка", "нож", "верёвка",
            "фонарик", "семена", "бензопила", "удочка", "топор", "компас"
        ]
        item = random.choice(items)
        
        skills = [
            "чинит всё", "делает операции", "готовит из ничего", "видит в темноте",
            "чувствует ложь", "вскрывает замки", "знает 5 языков", "отличный стрелок",
            "быстро бегает", "тихо ходит", "находит воду", "разводит огонь"
        ]
        skill = random.choice(skills)
        
        healths = [
            "абсолютно здоров", "здоров", "лёгкая аллергия", "близорукость",
            "астма", "диабет", "проблемы с сердцем", "хронический насморк"
        ]
        health = random.choice(healths)
        
        traits = [
            "агрессивный", "добрый", "тревожный", "спокойный", "харизматичный",
            "замкнутый", "эгоистичный", "альтруист", "оптимист", "пессимист"
        ]
        trait = random.choice(traits)
        
        secrets = [
            "ты агент КГБ", "ты убивал людей", "у тебя есть тайное убежище",
            "ты заражён", "ты сын миллиардера", "ты сидел в тюрьме",
            "у тебя есть пистолет", "ты не умеешь читать", "ты в розыске"
        ]
        secret = random.choice(secrets)
        
        return BunkerCharacter(
            age=age, gender=gender, profession=profession,
            item=item, skill=skill, health=health,
            trait=trait, secret=secret
        )
    
    async def generate_all_characters(self):
        """Отправляет роли в чат с упоминанием игрока"""
        for player in self.players.values():
            player.character = self.generate_random_character()
            
            await self.bot.send_message(
                self.chat_id,
                f"@{player.username}, твоя роль в бункере:\n{player.character.get_description()}",
                parse_mode="HTML"
            )
        
        self.generated_chars = True
        self.state = GameState.CHARACTERS_GENERATED
    
    async def start_discussion(self):
        """Начинает обсуждение на 4 минуты"""
        self.state = GameState.DISCUSSION
        self.discussion_start_time = datetime.now()
        
        await self.bot.send_message(
            self.chat_id,
            f"{E_MAGIC} <b>ВСЕ РОЛИ РОЗДАНЫ!</b> {E_MAGIC}\n\n"
            f"⏰ <b>у вас есть 4 минуты на обсуждение!</b>\n\n"
            f"💡 <b>советы:</b>\n"
            f"• обсуждайте кто полезен в бункере\n"
            f"• задавайте вопросы друг другу\n"
            f"• стройте стратегии\n"
            f"• НЕ ПОКАЗЫВАЙТЕ свои роли!\n\n"
            f"<i>через 4 минуты начнётся голосование!</i>",
            parse_mode="HTML"
        )
        
        asyncio.create_task(self.discussion_timer())
    
    async def discussion_timer(self):
        """Таймер 4 минуты"""
        await asyncio.sleep(240)
        
        if self.state == GameState.DISCUSSION:
            await self.bot.send_message(
                self.chat_id,
                f"{E_CAT_SURPRISED} <b>ВРЕМЯ ОБСУЖДЕНИЯ ЗАКОНЧИЛОСЬ!</b>\n\nначинаем голосование!",
                parse_mode="HTML"
            )
            await asyncio.sleep(2)
            self.state = GameState.ACTIVE
            from bot import start_bunker_round
            await start_bunker_round(self.chat_id)
    
    def get_alive_players(self) -> List[BunkerPlayer]:
        return [p for p in self.players.values() if p.is_alive]
    
    def get_players_to_eliminate(self) -> int:
        alive = len(self.get_alive_players())
        rules = {3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3}
        return rules.get(alive, 1)
    
    def get_voting_time(self) -> int:
        alive = len(self.get_alive_players())
        if alive <= 5:
            return 120
        else:
            return 180
    
    def can_start(self) -> bool:
        return 3 <= len(self.players) <= 10
