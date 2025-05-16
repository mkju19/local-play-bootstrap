from typing import Callable, Tuple, List, Dict, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sharpy.combat import Action
from sharpy.combat.zerg import MicroZerglings
from sharpy.knowledges import KnowledgeBot
from sharpy.managers.core import ManagerBase
from sharpy.managers.extensions import ChatManager
from sharpy.plans import BuildOrder
from sharpymicro.micro_matchup_tracker import MicroMatchupTracker


class MicroZerglings2(MicroZerglings):
    def __init__(self):
        self.surround_move = False
        super().__init__()

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        self.surround_move = False
        if len(self.enemies_near_by) == 1 and self.enemies_near_by.first.is_structure:
            building = self.enemies_near_by.first
            center = units.center
            if center.distance_to(building) > 1:
                self.surround_move = True
                return Action(center.towards(building.position, 2), False)

        return super().group_solve_combat(units, current_command)

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if not self.surround_move:
            if self.ready_to_shoot(unit) and len(self.enemies_near_by) == 1 and self.enemies_near_by.first.is_structure:
                building = self.enemies_near_by.first
                d = unit.position.distance_to(building)
                if d < unit.radius + 0.1 + building.radius:
                    return Action(self.enemies_near_by.first, True)
            return current_command

        if self.engage_ratio == 0:
            roaches = self.group.units.of_type(UnitTypeId.ROACH)
            if roaches:
                closest_roach = self.group.units.of_type(UnitTypeId.ROACH).closest_to(unit)
                pylons = self.cache.enemy(UnitTypeId.PYLON)
                if closest_roach and (not pylons or self.cache.enemy(UnitTypeId.PYLON).closest_distance_to(unit) > 10):
                    return Action(closest_roach, False)

        if len(self.enemies_near_by) == 1 and self.enemies_near_by.first.is_structure:
            if self.ready_to_shoot(unit):
                building = self.enemies_near_by.first
                d = unit.position.distance_to(building)
                if d < unit.radius + 0.1 + building.radius:
                    return Action(self.enemies_near_by.first, True)


        return super().unit_solve_combat(unit, current_command)

class SharpyMicroBot(KnowledgeBot):

    def __init__(self, build_name: str = "default"):
        super().__init__("sharpy-micro")
        self.chat_manager = ChatManager()
        self.tracker = MicroMatchupTracker()
        self.realtime_split = False

    def configure_managers(self) -> Optional[List[ManagerBase]]:
        self.roles.set_tag_each_iteration = True
        self.combat.default_rules.unit_micros[UnitTypeId.ZERGLING] = MicroZerglings2()
        return [self.chat_manager, self.tracker ]

    async def create_plan(self) -> BuildOrder:
        return BuildOrder([])

    async def on_step(self, iteration):
        await super().on_step(iteration)

        if self.time > 5:
            await self.chat_manager.chat_taunt_once("race", lambda: "Tag: " + str(self.race))

        if "BotMicroArena" in self.game_info.map_name:
            self.knowledge.pathing_manager.path_finder_terrain.create_block(self.game_info.map_center, (5, 5))

        if self.enemy_structures:
            self.combat.add_units(self.units)
            self.combat.execute(self.enemy_structures.first.position)
        elif self.enemy_units and self.units:
            self.combat.add_units(self.units)
            self.combat.execute(self.enemy_units.center)
            # if self.race == Race.Protoss:
            #     for unit in self.units:
            #         self.combat.add_unit(unit)
            #         target = self.pathing_manager.find_low_inside_ground(unit.position, self.enemy_units.closest_to(unit).position, 7)
            #         self.combat.execute(target, MoveType.Assault)
            # else:
            #     self.combat.add_units(self.units)
            #     self.combat.execute(self.enemy_units.center)

