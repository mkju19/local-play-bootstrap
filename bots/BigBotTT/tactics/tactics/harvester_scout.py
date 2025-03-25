from typing import Union, Set

from .steal_gas import ScoutStealGas
from managers.extended_unit_manager import ExtendedUnitManager
from sc2 import UnitTypeId, Race
from sc2.units import Units
from sharpy.managers.core.roles import UnitTask
from sharpy.plans.protoss import *
from sharpy.plans.tactics.scouting import ScoutBaseAction, ScoutAroundMain
from tactics import ScoutBlockNatural


class HarvesterScout(Scout):
    unit_manager: ExtendedUnitManager

    def __init__(self, steal_gas: bool = False):
        self.block_natural = ScoutBlockNatural()
        if steal_gas:
            super().__init__(
                UnitTypeId.PROBE,
                1,
                ScoutLocation.scout_own2(only_once=True),
                # ScoutLocation.scout_own3(only_once=True),
                # ScoutLocation.scout_own4(only_once=True),
                ScoutStealGas(),
                # self.block_natural, # Use this vs zerg or not?
                ScoutAroundMain(only_once=True),
                ScoutLocation.scout_enemy2(only_once=True),
                ScoutAroundMain(only_once=True),
                ScoutLocation.scout_enemy3(only_once=True),
                ScoutLocation.scout_enemy4(only_once=True),
                ScoutLocation.scout_enemy2(only_once=True),
            )
        else:
            super().__init__(
                UnitTypeId.PROBE,
                1,
                ScoutLocation.scout_own2(only_once=True),
                # ScoutLocation.scout_own3(only_once=True),
                # ScoutLocation.scout_own4(only_once=True),
                ScoutLocation.scout_enemy1(only_once=True),
                self.block_natural,  # Use this or not?
                ScoutAroundMain(only_once=True),
                ScoutLocation.scout_enemy2(only_once=True),
                ScoutAroundMain(only_once=True),
                ScoutLocation.scout_enemy3(only_once=True),
                ScoutLocation.scout_enemy4(only_once=True),
                ScoutLocation.scout_enemy2(only_once=True),
            )

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.unit_manager = self.knowledge.get_manager(ExtendedUnitManager)

    async def micro_units(self):
        if self.ended:
            self.roles.clear_tasks(self.units)
            self.scout_tags.clear()
            return True

        if self.knowledge.enemy_race != Race.Zerg:
            self.block_natural.ended = True

        if self.knowledge.enemy_race == Race.Terran:
            probe = self.units.first
            center = probe.position

            if probe.shield_health_percentage > 0.5:
                scvs = self.cache.enemy_in_range(center, 10)
                attack_these = Units([], self.ai)

                for scv in scvs:
                    if self.unit_manager.is_building(scv):
                        attack_these.append(scv)

                if attack_these:
                    closest = attack_these.closest_to(probe)
                    probe.attack(closest)
                    return True
        return await super().micro_units()

    def find_units(self) -> bool:
        if not self.started:

            free_units: Units = self.roles.get_types_from(self.unit_types, UnitTask.Building).idle

            if len(free_units) < self.unit_count:
                free_units.extend(
                    self.roles.get_types_from(self.unit_types, UnitTask.Idle, UnitTask.Moving, UnitTask.Gathering)
                )

            if len(free_units) >= self.unit_count:
                new_scouts = free_units.furthest_n_units(self.ai.start_location, self.unit_count)
                self.units.extend(new_scouts)
                self.scout_tags = new_scouts.tags

                self.started = True
        else:
            scouts = self.roles.get_types_from(self.unit_types, UnitTask.Scouting)
            self.units.extend(scouts.tags_in(self.scout_tags))
            if not self.units:
                # Scouts are dead, end the scout act
                self.ended = True
                return True
