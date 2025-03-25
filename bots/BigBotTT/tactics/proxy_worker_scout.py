from typing import Set

from sharpy import sc2math
from sharpy.managers.core import UnitRoleManager
from sharpy.managers.extensions.build_detector import EnemyRushBuild
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


class ProxyWorkerScout(ActBase):
    """
    Roams units during early game to look for proxies
    """

    def __init__(self):
        self.started = False
        self.ended = False
        self.scout_tags: Set[int] = set()
        self.roles: UnitRoleManager = None
        self.start_position: Point2 = None
        self.allowed_types = {UnitTypeId.STALKER, UnitTypeId.ADEPT, UnitTypeId.IMMORTAL, UnitTypeId.ZEALOT}
        self.scout_points: Set[Point2] = set()
        self.scout_count = 1
        self.proxy_found = False
        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
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
        if not self.scout_points and not self.scout_tags:
            # Nothing to scout anymore
            return True

        if (
            self.knowledge.lost_units_manager.calculate_own_lost_resources()[0] > 50
            or self.knowledge.build_detector.rush_build == EnemyRushBuild.WorkerRush
            or (self.proxy_found and not self.cache.enemy_in_range(self.start_position, 80).structure)
        ):
            self.stop_roam()
            return True

        if len(self.scout_tags) < self.scout_count:
            self.find_more_workers()

        if not self.scout_tags:
            self.stop_roam()
            return True

        stalkers = self.refresh_units()
        if not stalkers:
            return True

        self.roam_units(stalkers)
        return True

    def stop_roam(self):
        if self.scout_tags:
            units = self.roles.all_from_task(UnitTask.Fighting)
            units = units.tags_in(self.scout_tags)
            self.roles.clear_tasks(units)
            self.scout_points.clear()

    def find_more_workers(self):
        workers = self.roles.free_workers
        if workers:
            workers = workers.sorted_by_distance_to(self.start_position)

        for worker in workers:  # type: Unit
            self.scout_tags.add(worker.tag)
            self.roles.set_task(UnitTask.Fighting, worker)
            return

    def refresh_units(self) -> Units:
        units = self.roles.all_from_task(UnitTask.Fighting)
        units = units.tags_in(self.scout_tags)
        self.scout_tags = units.tags
        self.roles.set_tasks(UnitTask.Fighting, units)
        return units

    def roam_units(self, units: Units):
        median: Point2 = sc2math.unit_geometric_median(units)
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
            self.scout_count = 3
            self.proxy_found = True
            # if close_buildings(UnitTypeId.ROBOTICSFACILITY):
            #     # It's too dangerous to fight against proxy robo
            #     self.stop_roam()
            building = close_buildings.closest_to(median)
            self.combat.add_units(units)
            self.combat.execute(building.position)
            return

        if best_point:
            self.combat.add_units(units)
            self.combat.execute(best_point)
            return

        self.stop_roam()
