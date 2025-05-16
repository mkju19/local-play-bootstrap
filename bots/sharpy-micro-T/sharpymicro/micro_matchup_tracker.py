from typing import Dict, List, Optional

from sc2.bot_ai import BotAI
from sc2.data import Result
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sharpy.interfaces import IUnitCache
from sharpy.managers import ManagerBase
from sharpy.managers.core import EnemyUnitsManager
from sharpy.managers.extensions import ChatManager


class MatchupState:
    own_units_at_start: Dict[UnitTypeId, int]
    enemy_units_at_start: Dict[UnitTypeId, int]

    own_units_at_end: Dict[UnitTypeId, int]
    enemy_units_at_end: Dict[UnitTypeId, int]

    def __init__(self):
        self.start_time = 0
        self.end_time = 0

        self.own_units_at_start: Dict[UnitTypeId, int] = {}
        self.enemy_units_at_start: Dict[UnitTypeId, int] = {}

        self.own_units_at_end: Dict[UnitTypeId, int] = {}
        self.enemy_units_at_end: Dict[UnitTypeId, int] = {}
        super().__init__()

    def init(self, cache: IUnitCache):
        for unit_type in cache.own_unit_cache:
            self.own_units_at_start[unit_type] = len(cache.own_unit_cache[unit_type])
            self.own_units_at_end[unit_type] = len(cache.own_unit_cache[unit_type])

        for unit_type in cache.enemy_unit_cache:
            self.enemy_units_at_start[unit_type] = len(cache.enemy_unit_cache[unit_type])
            self.enemy_units_at_end[unit_type] = len(cache.enemy_unit_cache[unit_type])

    def update(self, cache: IUnitCache):
        self.own_units_at_end.clear()
        self.enemy_units_at_end.clear()

        for unit_type in cache.own_unit_cache:
            self.own_units_at_end[unit_type] = len(cache.own_unit_cache[unit_type])
        for unit_type in cache.enemy_unit_cache:
            self.enemy_units_at_end[unit_type] = len(cache.enemy_unit_cache[unit_type])


class MicroMatchupTracker(ManagerBase):
    enemy_units_manager: EnemyUnitsManager
    matchups: List[MatchupState]
    active_matchup: Optional[MatchupState]
    chat_manager: ChatManager
    round_count: int

    def __init__(self):
        super().__init__()
        self.matchups = []
        self.active_matchup = None
        self.round_count = 10

    async def start(self, knowledge: "Knowledge"):
        self.chat_manager = knowledge.get_required_manager(ChatManager)
        await super().start(knowledge)

    async def update(self):
        if self.ai.state.game_loop == 0:
            neutral_units = self.ai.all_units.filter(lambda u: not u.is_enemy and not u.is_mine)

            if len(neutral_units) > 1:
                self.round_count = len(neutral_units)
            else:
                self.round_count = 10

        neural_active = False

        for unit in self.ai.all_units:
            if unit.has_buff(BuffId.NEURALPARASITE):
                neural_active = True
                break

        if neural_active or len(self.ai.units) > 0 or len(self.ai.enemy_units) > 0:
            # Round active
            if self.active_matchup is not None:
                self.active_matchup.update(self.knowledge.unit_cache)
            else:
                self.active_matchup = MatchupState()
                self.active_matchup.start_time = self.ai.time
                self.active_matchup.init(self.knowledge.unit_cache)
        else:
            # Round over / not started yet
            if self.active_matchup is not None:
                # self.active_matchup.update(self.knowledge.unit_cache)
                self.matchups.append(self.active_matchup)
                self.active_matchup.end_time = self.ai.time
                round_number = len(self.matchups)
                has_own = len(self.active_matchup.own_units_at_end) > 0
                has_enemy = len(self.active_matchup.enemy_units_at_end) > 0

                if (has_enemy and has_own) or (not has_enemy and not has_own):
                    await self.chat_manager.chat_taunt_once(
                        "round" + str(round_number), lambda: f"Tag: Round {round_number} - Tie"
                    )
                elif has_own:
                    await self.chat_manager.chat_taunt_once(
                        "round" + str(round_number), lambda: f"Tag: Round {round_number} - Won"
                    )
                else:
                    await self.chat_manager.chat_taunt_once(
                        "round" + str(round_number), lambda: f"Tag: Round {round_number} - Lost"
                    )

                self.active_matchup = None

                if round_number == self.round_count:
                    text = ""

                    for matchup in self.matchups:
                        if len(matchup.enemy_units_at_end) == 0:
                            if len(matchup.own_units_at_end) == 0:
                                text += "t"
                            else:
                                text += "w"
                        else:
                            text += "l"

                    await self.chat_manager.chat_taunt_once(
                        "end-tag", lambda: f"Tag: {text}"
                    )

    async def on_end(self, game_result: Result):
        if self.active_matchup is not None:
            self.matchups.append(self.active_matchup)
            self.active_matchup.end_time = self.ai.time
            self.active_matchup = None
        self.print_contents()

    def print_contents(self):
        number = 1
        own_score = 0
        enemy_score = 0
        tie_score = 0
        rounds_won = []

        self.print("Matchups:", False)
        for matchup in self.matchups:
            own_units = 0
            enemy_units = 0
            duration = (matchup.end_time - matchup.start_time) * 1.4
            self.print("Matchup " + str(number) + " Duration: " + str(round(duration, 1)) + " s", False)

            for unit_type in matchup.own_units_at_start:
                count = matchup.own_units_at_start[unit_type]
                self.print(f"{unit_type} - {count}", False)
            self.print("vs", False)
            for unit_type in matchup.enemy_units_at_start:
                count = matchup.enemy_units_at_start[unit_type]
                self.print(f"{unit_type} - {count}", False)

            self.print("Result:", False)
            for unit_type in matchup.own_units_at_end:
                count = matchup.own_units_at_end[unit_type]
                own_units += count
                self.print(f"{unit_type} - {count}", False)
            if own_units == 0:
                self.print("None", False)
            self.print("vs", False)
            for unit_type in matchup.enemy_units_at_end:
                count = matchup.enemy_units_at_end[unit_type]
                enemy_units += count
                self.print(f"{unit_type} - {count}", False)
            if enemy_units == 0:
                self.print("None", False)

            if own_units > 0 and enemy_units == 0:
                own_score += 1
                rounds_won.append(number)
            elif own_units == 0 and enemy_units > 0:
                enemy_score += 1
            else:
                tie_score += 1
            number += 1

        self.print(f"Final Result: {own_score} - {enemy_score} Ties: {tie_score} Rounds Won {rounds_won}", False)

    async def post_update(self):
        pass
