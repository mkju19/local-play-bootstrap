from typing import Optional

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sharpy.general.zone import Zone
from sharpy.interfaces import IGatherPointSolver, IZoneManager
from sharpy.managers.core import UnitValue
from sharpy.plans.acts import ActBase
from sharpy.tools import IntervalFunc
from sc2.position import Point2
from sc2.unit import Unit

from sharpy.knowledges import Knowledge

from sc2.units import Units


class PlanGatherOptimizer(ActBase):
    """
    Moves knowledge.gather_point to the base that is closest to enemy
    """

    gather_point_solver: IGatherPointSolver
    zone_manager: IZoneManager

    def __init__(self):
        self.gather_point: Point2 = None
        self.updater: IntervalFunc = None
        self.enabled = True  # Allows disabling gather point setter for proxies for example
        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        # We don't need to update the gather point every frame
        self.updater = IntervalFunc(self.ai, self.update_gather_point, 0.5)
        self.gather_point_solver = knowledge.get_required_manager(IGatherPointSolver)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)
        self.gather_point = self.gather_point_solver.gather_point

    async def execute(self) -> bool:
        if self.enabled:
            self.knowledge.gather_point = self.updater.execute()
        return True

    def update_gather_point(self) -> Point2:
        gather_point = self.gather_point_solver.gather_point
        enemies: Units = self.ai.all_enemy_units
        enemies = enemies.filter(self.filter_unit)

        if not enemies:
            # impossible to figure out a enemy center
            # Let's use enemy zone gather points instead
            enemy_center = self.zone_manager.enemy_start_location
            for zone in self.zone_manager.enemy_expansion_zones:
                if zone.is_enemys:
                    enemy_center = zone.gather_point
        else:
            enemy_center = enemies.center

        best_distance: Optional[float] = None
        for zone in self.zone_manager.expansion_zones:  # type: Zone
            if zone.is_ours:
                d = zone.gather_point.distance_to(enemy_center)
                # TODO: Use pathfinding to determine distances?
                # path = zone.paths.get(natural?)
                if best_distance is None or d < best_distance:
                    gather_point = zone.gather_point
                    if zone.zone_index == 1 and zone.our_wall():
                        if zone.ramp:
                            gather_point = zone.ramp.top_center.towards(zone.center_location, 6)
                        else:
                            wall_buildings = self.cache.own_in_range(gather_point, 4).of_type(
                                {UnitTypeId.CYBERNETICSCORE, UnitTypeId.GATEWAY}
                            )
                            if wall_buildings:
                                gather_point = wall_buildings.closest_to(zone.center_location).position.towards(
                                    zone.center_location, 4
                                )
                        zone.gather_point = gather_point
                    best_distance = d

        return gather_point

    def filter_unit(self, unit: Unit) -> bool:
        if unit.is_structure:
            return False
        if unit.type_id in self.unit_values.combat_ignore:
            return False
        if unit.type_id in UnitValue.worker_types:
            return False
        return True
