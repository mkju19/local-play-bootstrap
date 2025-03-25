from typing import Callable, List, Set

from sc2 import UnitTypeId
from sc2.constants import ALL_GAS
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sharpy.plans.tactics.scouting.scout_base_action import ScoutBaseAction

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sharpy.knowledges import Knowledge


class ScoutStealGas(ScoutBaseAction):
    def __init__(self) -> None:
        self.gas_locations: List[Point2] = []
        super().__init__(True)

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)

    async def execute(self) -> bool:
        if self.ended:
            return True
        if not self._units:
            return False

        enemy_main = self.zone_manager.expansion_zones[-1]
        geysers = self.ai.vespene_geyser.closer_than(15, enemy_main.center_location)

        empty_geysers: Units = Units([], self.ai)

        for geyser in geysers:
            if not self.cache.enemy_in_range(geyser.position, 1).of_type(ALL_GAS):
                empty_geysers.append(geyser)

        if not empty_geysers or self.cache.own_in_range(enemy_main.center_location, 15).of_type(ALL_GAS):
            self.ended = True
            return True

        center = self._units.center
        closest = empty_geysers.closest_to(center)

        if center.distance_to(closest) < 5:
            # Build gas
            worker = self._units.first
            worker.build_gas(closest)
        else:
            target = self.pather.find_influence_ground_path(center, closest.position)
            for unit in self._units:
                unit.move(target)

        return False
