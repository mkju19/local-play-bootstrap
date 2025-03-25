from typing import Set

from sharpy import sc2math
from sharpy.managers.core import UnitRoleManager
from sharpy.managers.extensions.build_detector import EnemyRushBuild, BuildDetector
from sharpy.plans.acts import ActBase
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

from sharpy.knowledges import Knowledge

from sharpy.managers.core.roles import UnitTask
from sc2.units import Units


class StalkerRoam(ActBase):
    """
    Roams units during early game to look for proxies
    """

    def __init__(self):
        self.started = False
        self.ended = False
        self.scout_tags: Set[int] = set()
        self.roles: UnitRoleManager = None
        self.start_position: Point2 = None
        self.allowed_types = {UnitTypeId.STALKER, UnitTypeId.IMMORTAL, UnitTypeId.ZEALOT}
        self.scout_points: Set[Point2] = set()
        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.build_detector = knowledge.get_required_manager(BuildDetector)
        self.roles = self.roles
        self.start_position = self.zone_manager.expansion_zones[1].center_location

        r = 5
        for zone in self.zone_manager.expansion_zones[1:6]:
            center: Point2 = zone.center_location
            self.scout_points.add(center)
            self.scout_points.add(center.offset((r, 0)))
            self.scout_points.add(center.offset((-r, 0)))
            self.scout_points.add(center.offset((0, r)))
            self.scout_points.add(center.offset((0, -r)))

    async def execute(self) -> bool:
        if self.ended or (not self.scout_points and not self.scout_tags):
            # Nothing to scout anymore
            return True

        if (
            self.cache.enemy(UnitTypeId.NEXUS).amount != 1
            or self.lost_units_manager.calculate_own_lost_resources()[0] > 400
            or self.build_detector.rush_build == EnemyRushBuild.WorkerRush
        ):
            self.ended = True
            self.stop_roam()
            return True

        if len(self.scout_tags) < 2:
            self.find_more_stalkers()

        if not self.scout_tags:
            self.stop_roam()
            return True

        stalkers = self.refresh_stalkers()
        if not stalkers:
            return True

        self.roam_stalkers(stalkers)
        return True

    def stop_roam(self):
        if self.scout_tags:
            units = self.roles.all_from_task(UnitTask.Fighting)
            units = units.tags_in(self.scout_tags)
            self.roles.clear_tasks(units)
            if self.ai.time > 4 * 60 or self.roles.all_from_task(UnitTask.Attacking):
                # Stop roam in case we are going for attack
                self.scout_points.clear()

    def find_more_stalkers(self):
        idle_stalkers = self.roles.idle.of_type(self.allowed_types)
        if idle_stalkers:
            idle_stalkers = idle_stalkers.sorted_by_distance_to(self.start_position)

        for stalker in idle_stalkers:  # type: Unit
            self.scout_tags.add(stalker.tag)
            self.roles.set_task(UnitTask.Fighting, stalker)
            # if len(self.scout_tags) > 2:
            #     return

    def refresh_stalkers(self) -> Units:
        units = self.roles.all_from_task(UnitTask.Fighting)
        units = units.tags_in(self.scout_tags)
        self.scout_tags = units.tags
        self.roles.set_tasks(UnitTask.Fighting, units)
        return units

    def roam_stalkers(self, stalkers: Units):
        median: Point2 = sc2math.unit_geometric_median(stalkers)
        remove_points = []
        best_point = None
        best_distance = 0

        for point in self.scout_points:
            if self.ai.is_visible(point):
                remove_points.append(point)
            else:
                d = median.distance_to_point2(point)
                if not best_point or d < best_distance:
                    best_distance = d
                    best_point = point

        for remove_point in remove_points:
            self.scout_points.remove(remove_point)

        close_buildings = self.cache.enemy_in_range(self.start_position, 80).structure
        if close_buildings:
            # if close_buildings(UnitTypeId.ROBOTICSFACILITY):
            #     # It's too dangerous to fight against proxy robo
            #     self.stop_roam()
            building = close_buildings.closest_to(median)
            self.combat.add_units(stalkers)
            self.combat.execute(building.position)
            return

        if best_point:
            self.combat.add_units(stalkers)
            self.combat.execute(best_point)
            return

        self.stop_roam()
