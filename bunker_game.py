import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from database import update_xp, get_xp

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
        """Полное описание персонажа для игрока"""
        desc = f"""
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
💡 <i>твоя задача - убедить других, что ты полезен в бункере</i>
"""
        return desc

class GameState(Enum):
    WAITING = "waiting"
    CHARACTERS_GENERATED = "characters_generated"
    ACTIVE = "active"
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
        self.lobby_message_id = None
        self.generated_chars = False
        
    def generate_random_character(self) -> BunkerCharacter:
        """Генерирует рандомного персонажа с уникальными характеристиками"""
        
        # Возраст от 6 до 90
        age = random.randint(6, 90)
        
        # Пол
        genders = ["мужчина", "женщина", "небинарная персона"]
        gender = random.choice(genders)
        
        # Профессии (разнообразные)
        professions = [
            "врач-хирург", "военный снайпер", "инженер-робототехник", 
            "шеф-повар", "фермер-растениевод", "механик дизельных двигателей",
            "электрик высоковольтных сетей", "строитель-высотник", 
            "охотник на медведей", "рыбак промышленник", "химик-фармацевт",
            "программист AI", "школьный учитель", "дальнобойщик", 
            "сантехник", "пожарный", "полицейский", "адвокат",
            "бизнесмен", "художник", "музыкант", "археолог",
            "геолог", "биолог", "ветеринар", "стоматолог",
            "пилот", "моряк", "шахтер", "кузнец"
        ]
        profession = random.choice(professions)
        
        # Предметы (странные и полезные)
        items = [
            "зажигалка Zippo", "молоток с зубилом", "полная аптечка", 
            "банка тушёнки (3 кг)", "охотничий нож", "альпинистская верёвка",
            "тактический фонарик", "карта метро 2024", "семена пшеницы",
            "бензопила", "удочка с запасом лески", "книга 'Как выжить в аду'",
            "фляга с самогоном", "бинты и антисептик", "гаечный ключ",
            "аккумулятор 12V", "газета 10-летней давности", "компас",
            "рация", "противогаз", "набор отмычек", "баллончик с перцем",
            "палатка", "спальник", "котелок", "топор"
        ]
        item = random.choice(items)
        
        # Навыки (полезные и бесполезные)
        skills = [
            "может починить любой двигатель", "умеет делать операции вслепую",
            "готовит из крыс стейк", "видит в темноте", "чувствует ложь",
            "умеет вскрывать замки", "знает 7 языков", "отличный стрелок",
            "быстрее всех бегает", "тише всех ходит", "умеет предсказывать погоду",
            "находит воду везде", "разводит огонь палочками", "лечит травами",
            "дрессирует животных", "умеет танцевать тверк", "играет на балалайке",
            "рассказывает лучшие анекдоты", "помнит всё что прочитал"
        ]
        skill = random.choice(skills)
        
        # Здоровье
        healths = [
            "абсолютно здоров", "здоров как бык", "здоров",
            "лёгкая аллергия на пыльцу", "близорукость", "дальнозоркость",
            "астма", "диабет", "проблемы с сердцем", "эпилепсия",
            "хронический насморк", "ломаная нога плохо срослась",
            "потерял палец на руке", "шум в ушах", "мигрень",
            "язва желудка", "алкоголизм", "курит пачку в день"
        ]
        health = random.choice(healths)
        
        # Характер
        traits = [
            "агрессивный и вспыльчивый", "добрый и отзывчивый", 
            "тревожный и мнительный", "спокойный как удав", 
            "харизматичный манипулятор", "замкнутый интроверт", 
            "эгоистичный нарцисс", "альтруист помогающий всем",
            "параноик везде видящий заговор", "оптимист до безумия", 
            "пессимист всё предрекающий", "ленивый лежебока", 
            "работяга до седьмого пота", "трус прячущийся за спины",
            "смельчак лезущий на амбразуру"
        ]
        trait = random.choice(traits)
        
        # Тайна (скрытая информация)
        secrets = [
            "на самом деле ты агент КГБ", "ты убил трёх человек в прошлом",
            "у тебя есть карта с тайным убежищем", "ты заражён вирусом",
            "ты сын миллиардера", "ты сидел в тюрьме 10 лет",
            "у тебя есть пистолет (никто не знает)", "ты не умеешь читать",
            "ты в розыске", "ты работал на правительство",
            "у тебя аллергия на людей", "ты видишь мёртвых",
            "ты можешь общаться с животными", "ты бессмертный (вроде)",
            "у тебя есть тайная лаборатория", "ты из будущего",
            "ты рептилоид", "ты вампир (пьёшь кровь)"
        ]
        secret = random.choice(secrets)
        
        return BunkerCharacter(
            age=age, gender=gender, profession=profession,
            item=item, skill=skill, health=health,
            trait=trait, secret=secret
        )
    
    async def generate_all_characters(self):
        """Генерирует персонажей для всех игроков и отправляет в личку"""
        for player in self.players.values():
            player.character = self.generate_random_character()
            
            # Отправляем ТОЛЬКО этому игроку в личное сообщение!
            try:
                await self.bot.send_message(
                    player.user_id,
                    player.character.get_description(),
                    parse_mode="HTML"
                )
                await self.bot.send_message(
                    player.user_id,
                    f"{E_MAGIC} <b>твоя цель - выжить в бункере!</b>\n\n"
                    f"💡 <i>никому не рассказывай свою роль\n"
                    f"докажи что ты полезен для группы</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение {player.username}: {e}")
        
        self.generated_chars = True
        self.state = GameState.CHARACTERS_GENERATED
    
    def get_alive_players(self) -> List[BunkerPlayer]:
        """Возвращает живых игроков"""
        return [p for p in self.players.values() if p.is_alive]
    
    def get_players_to_eliminate(self) -> int:
        """Сколько игроков выгнать в этом раунде"""
        alive = len(self.get_alive_players())
        
        # Правила выгоняния
        rules = {
            3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3, 12: 3
        }
        return rules.get(alive, 1)
    
    def get_voting_time(self) -> int:
        """Время на голосование в секундах"""
        alive = len(self.get_alive_players())
        if alive <= 5:
            return 120  # 2 минуты
        else:
            return 180  # 3 минуты
    
    def can_start(self) -> bool:
        """Можно ли начинать игру"""
        return 3 <= len(self.players) <= 12


# Импортируем эмодзи (нужно добавить в начало файла)
from enderia import E_CROWN, E_MAGIC, E_HOUSE, E_HEART, E_CAT_SURPRISED, E_CAT_DANCE, E_NOTE
