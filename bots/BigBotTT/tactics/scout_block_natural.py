from typing import Callable, List

from sc2.position import Point2
from sharpy.plans.tactics.scouting.scout_base_action import ScoutBaseAction

from typing import TYPE_CHECKING

from sharpy.sc2math import points_on_circumference_sorted

if TYPE_CHECKING:
    from sharpy.knowledges import Knowledge


class ScoutBlockNatural(ScoutBaseAction):
    scout_locations: List[Point2]

    def __init__(self, time_end: float = 240, distance_to_reach: float = 5, only_once: bool = False) -> None:
        super().__init__(only_once)
        self.time_end = time_end
        self.distance_to_reach = distance_to_reach
        self.main_target = Point2((0, 0))
        self.scout_locations = []

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.main_target = self.zone_manager.enemy_expansion_zones[1].center_location

    async def execute(self) -> bool:
        if self.ended:
            return True
        if not self._units:
            return False

        if self.ai.time > self.time_end:
            self.ended = True
            return True

        center = self._units.center

        if center.distance_to(self.main_target) < 10 and not self.scout_locations:
            self.scout_locations = points_on_circumference_sorted(self.main_target, center, 2.5, 16)

        if self.scout_locations:
            self.current_target = self.scout_locations[0]
        else:
            self.current_target = self.main_target

        if self._units[0].is_flying:
            target = self.pather.find_influence_air_path(center, self.current_target)
        else:
            target = self.pather.find_influence_ground_path(center, self.current_target)

        for unit in self._units:
            unit.move(target)

        if center.distance_to(self.current_target) < 0.5:
            if self.scout_locations:
                self.scout_locations.remove(self.current_target)
                if self.cache.enemy_in_range(self.main_target, 3).structure or self._units[0].health_percentage < 0.5:
                    self.ended = True
                    return True
        return False
