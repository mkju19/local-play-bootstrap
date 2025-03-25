from math import floor
from typing import List, Tuple, Dict, Optional

from sharpy.managers.core.zone_manager import MapName, ZoneManager
from .extended_build_detector import ExtendedBuildDetector
from .state_analyzer import StateAnalyzer
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2pathlib import MapType
from sharpy.general.zone import Zone
from sharpy.managers.core import BuildingSolver, PathingManager
from sharpy.managers.core.grids import BuildArea, ZoneArea, GridArea, Rectangle, BlockerType

REAPER_WALL_POSITIONS: Dict[MapName, List[List[Point2]]] = {
    MapName.Example: [
        # Gate1, pylon1, Gate2, Optional pylon2
        [Point2((0, 0)), Point2((0, 0)), Point2((0, 0))],
        [Point2((0, 0)), Point2((0, 0)), Point2((0, 0))],
    ],
    MapName.IceandChromeLE: [
        [Point2((87.5, 77.5)), Point2((88, 75)), Point2((89.5, 72.5))],
        [Point2((164.5, 165.5)), Point2((167, 164)), Point2((168.5, 161.5))],
    ],
    MapName.DeathAuraLE: [
        [Point2((46.5, 128.5)), Point2((49, 130)), Point2((51.5, 131.5))],
        [Point2((140.5, 56.5)), Point2((143, 58)), Point2((145.5, 59.5))],
    ],
    MapName.EverDreamLE: [
        [Point2((61.5, 67.5)), Point2((64.0, 63.0)), Point2((64.5, 67.5))],
        [Point2((135.5, 144.5)), Point2((136.0, 149.0)), Point2((138.5, 144.5))],
    ],
    MapName.SubmarineLE: [
        [Point2((48.5, 124.5)), Point2((48.0, 122.0)), Point2((48.5, 117.5)), Point2((48.0, 120.0)),],
        [Point2((119.5, 46.5)), Point2((120.0, 44.0)), Point2((119.5, 39.5)), Point2((120.0, 42.0)),],
    ],
    MapName.EternalEmpireLE: [
        [Point2((128.5, 129.5)), Point2((130.0, 127.0)), Point2((131.5, 124.5))],
        [Point2((44.5, 47.5)), Point2((46.0, 45.0)), Point2((47.5, 42.5))],
    ],
    MapName.GoldenWallLE: [
        [Point2((28.5, 66.5)), Point2((31.0, 66.0)), Point2((33.5, 64.5))],
        [Point2((179.5, 66.5)), Point2((177.0, 66.0)), Point2((174.5, 64.5))],
    ],
    MapName.PillarsofGoldLE: [
        [Point2((44.5, 49.5)), Point2((47.0, 48.0)), Point2((47.5, 45.5))],
        [Point2((123.5, 122.5)), Point2((121.0, 124.0)), Point2((120.5, 126.5))],
    ],
    MapName.AscensiontoAiurLE: [
        [Point2((17.5, 120.5)), Point2((20.0, 120.0)), Point2((22.5, 120.5)), Point2((25.0, 120.0)),],
        [Point2((158.5, 31.5)), Point2((156.0, 32.0)), Point2((153.5, 31.5)), Point2((151.0, 32.0)),],
    ],
    MapName.RomanticideLE: [
        [Point2((142.5, 44.5)), Point2((144.0, 47.0)), Point2((146.5, 47.5)), Point2((147.0, 50.0))],
        [Point2((57.5, 127.5)), Point2((56.0, 125.0)), Point2((53.5, 124.5)), Point2((53.0, 122.0))],
    ],
    MapName.Atmospheres2000: [
        [Point2((148.5, 138.5)), Point2((149.0, 136.0)), Point2((151.5, 134.5))],
        [Point2((72.5, 69.5)), Point2((75.0, 68.0)), Point2((75.5, 65.5))],
    ],
    MapName.Blackburn: [
        # Gate1, pylon1, Gate2, Optional pylon2
        [Point2((56.5, 29.5)), Point2((59.0, 28.0)), Point2((59.5, 25.5))],
        [Point2((125.5, 25.5)), Point2((125.0, 28.0)), Point2((127.5, 29.5))],
    ],
    MapName.Jagannatha: [
        # Gate1, pylon1, Gate2, Optional pylon2
        [Point2((51.5, 51.5)), Point2((54.0, 51.0)), Point2((53.5, 48.5))],
        [Point2((116.5, 134.5)), Point2((114.0, 135.0)), Point2((114.5, 137.5))],
    ],
    MapName.Lightshade: [
        # Gate1, pylon1, Gate2, Optional pylon2
        [Point2((128.5, 43.5)), Point2((131.0, 45.0)), Point2((132.5, 47.5))],
        [Point2((55.5, 120.5)), Point2((53.0, 119.0)), Point2((51.5, 116.5))],
    ],
    MapName.Oxide: [
        # Gate1, pylon1, Gate2, Optional pylon2
        [Point2((138.5, 134.5)), Point2((136.0, 135.0)), Point2((133.5, 136.5))],
        [Point2((53.5, 69.5)), Point2((56.0, 69.0)), Point2((58.5, 67.5))],
    ],
}


class BuildingPlaceOptimizer(BuildingSolver):
    state_analyzer: StateAnalyzer
    build_detector: ExtendedBuildDetector
    temp2x2: List[Point2]
    temp3x3: List[Point2]

    @property
    def buildings3x3(self) -> List[Point2]:
        return self.temp3x3

    @property
    def buildings2x2(self) -> List[Point2]:
        return self.temp2x2

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.pather = knowledge.get_required_manager(PathingManager)
        self.state_analyzer = knowledge.get_required_manager(StateAnalyzer)
        self.build_detector = knowledge.get_required_manager(ExtendedBuildDetector)
        if len(self.zone_manager.expansion_zones) > 3:
            self.color_zone(self.zone_manager.expansion_zones[3], ZoneArea.OwnFourthZone)
        if len(self.zone_manager.expansion_zones) > 4:
            self.color_zone(self.zone_manager.expansion_zones[4], ZoneArea.OwnFifthZone)

    async def solve_grid(self):
        if self.ai.enemy_race == Race.Terran and self.ai.race == Race.Protoss:
            self.anti_reaper_wall()
        await super().solve_grid()

    def anti_reaper_wall(self):
        zone_manager = self.knowledge.get_required_manager(ZoneManager)
        positions = REAPER_WALL_POSITIONS.get(zone_manager.map, None)
        if positions:
            if self.ai.start_location.distance_to(positions[0][0]) < self.ai.start_location.distance_to(
                positions[1][0]
            ):
                pos = positions[0]
            else:
                pos = positions[1]

            self.fill_and_save(pos[0], BlockerType.Building3x3, BuildArea.Building)
            self.fill_and_save(pos[1], BlockerType.Building2x2, BuildArea.Pylon)
            self.fill_and_save(pos[2], BlockerType.Building3x3, BuildArea.Building)
            self.set_deadzone(pos[0], BlockerType.Building5x5)
            self.set_deadzone(pos[1], BlockerType.Building4x4)
            self.set_deadzone(pos[2], BlockerType.Building5x5)
            if len(pos) > 3:
                self.fill_and_save(pos[1], BlockerType.Building2x2, BuildArea.Pylon)
                self.fill_and_save(pos[3], BlockerType.Building2x2, BuildArea.Pylon)
                self.set_deadzone(pos[3], BlockerType.Building4x4)

    def set_deadzone(self, pos: Point2, blocker_type: BlockerType):
        def remove_connection(cell: GridArea, point: Point2) -> GridArea:
            self.pather.map.remove_connection(point)
            return cell

        rect = self.grid.get_area(pos, blocker_type)
        self.grid.fill_rect_func(rect, remove_connection)

    async def update(self):
        await super().update()

        if self.state_analyzer.cannon_ready or self.build_detector.worker_rush_detected:
            await self.evade_cannon_buildings()
        elif not self.zone_manager.expansion_zones[0].is_ours:
            await self.main_lost_buildings()
        else:
            self.temp2x2 = super().buildings2x2
            self.temp3x3 = super().buildings3x3
            self.insert_pylon_on_second()

        return super().buildings3x3

    async def main_lost_buildings(self):
        own_zones = []
        for zone in self.zone_manager.expansion_zones:
            if zone.is_ours:
                own_zones.append(zone.zone_index + 1)

        def order_by(pos: Point2):
            # Build away from main
            return 1 - pos.distance_to(self.ai.start_location) - self.pather.map.current_influence(MapType.Ground, pos)

        buildings = []
        bad_buildings = []
        for pos in self._building_positions.get(BuildArea.Pylon, []):
            if self.pather.map.get_zone(pos) not in own_zones:
                bad_buildings.append(pos)
            else:
                buildings.append(pos)

        buildings.sort(key=order_by)
        buildings.extend(bad_buildings)
        self.temp2x2 = buildings
        buildings = []
        bad_buildings = []
        for pos in self._building_positions.get(BuildArea.Building, []):
            if self.pather.map.get_zone(pos) not in own_zones:
                bad_buildings.append(pos)
            else:
                buildings.append(pos)

        buildings.sort(key=order_by)
        buildings.extend(bad_buildings)
        self.temp3x3 = buildings

    async def evade_cannon_buildings(self):
        cannons = self.cache.enemy(UnitTypeId.PHOTONCANNON)
        closest_cannon = None
        if cannons:
            closest_cannon = cannons.closest_to(self.ai.start_location)

        def order_by(pos: Point2):
            return 10 - pos.distance_to(closest_cannon)

        buildings = []
        bad_buildings = []
        for pos in self._building_positions.get(BuildArea.Pylon, []):
            zone_index = self.pather.map.get_zone(pos)
            if self.pather.map.current_influence(MapType.Ground, pos) > 100 or zone_index != 1:
                bad_buildings.append(pos)
            else:
                buildings.append(pos)
        if closest_cannon:
            buildings.sort(key=order_by)
        buildings.extend(bad_buildings)
        self.temp2x2 = buildings
        buildings = []
        bad_buildings = []
        for pos in self._building_positions.get(BuildArea.Building, []):
            if self.pather.map.current_influence(MapType.Ground, pos) > 100 or self.pather.map.get_zone(pos) != 1:
                bad_buildings.append(pos)
            else:
                buildings.append(pos)
        if closest_cannon:
            buildings.sort(key=order_by)
        buildings.extend(bad_buildings)
        self.temp3x3 = buildings

    def color_zone(self, zone: Zone, zone_type: ZoneArea):
        center = Point2((floor(zone.center_location.x), floor(zone.center_location.y)))

        radius = 30  # zone.radius
        zone_index = self.pather.map.get_zone(zone.center_location)

        def fill_circle(cell: GridArea, point: Point2) -> GridArea:
            if cell.Area == BuildArea.Empty and zone_index == self.pather.map.get_zone(point):
                cell.ZoneIndex = zone_type

            return cell

        rect = Rectangle(center.x - radius, center.y - radius, radius * 2, radius * 2)
        self.grid.fill_rect_func(rect, fill_circle)

    def solve_buildings(self):
        start: Point2 = self.zone_manager.own_main_zone.center_location
        zone: Zone = self.zone_manager.own_main_zone
        zone_color = ZoneArea.OwnMainZone
        self.fill_zone(zone.center_location, zone_color)

        if self.knowledge.my_race == Race.Terran:
            list = self._building_positions.get(BuildArea.Building)
            list.sort(key=lambda k: start.distance_to_point2(k))

        zone: Zone = self.zone_manager.expansion_zones[1]
        zone_color = ZoneArea.OwnNaturalZone
        self.fill_zone(zone.center_location, zone_color)

        zone: Zone = self.zone_manager.expansion_zones[2]
        zone_color = ZoneArea.OwnThirdZone
        self.fill_zone(zone.center_location, zone_color)

        zone: Zone = self.zone_manager.expansion_zones[3]
        zone_color = ZoneArea.OwnFourthZone
        self.fill_zone(zone.center_location, zone_color)

        if len(self.zone_manager.expansion_zones) > 4:
            zone: Zone = self.zone_manager.expansion_zones[4]
            zone_color = ZoneArea.OwnFifthZone
            self.fill_zone(zone.center_location, zone_color)

    def insert_pylon_on_second(self) -> None:
        main = self.zone_manager.expansion_zones[0]
        zone = self.zone_manager.expansion_zones[1]
        enemy_main_index = self.zone_manager.expansion_zones[-1].zone_index

        if (
            main.is_ours
            and zone.is_ours
            and zone.assaulting_enemy_power.power < 1
            and len(zone.our_units.of_type(UnitTypeId.PYLON)) < 1
        ):
            target_pos = zone.paths[enemy_main_index].get_index(4)
            if not target_pos:
                return
            best_distance = 999
            best_point: Optional[Point2] = None

            for point in self._building_positions.get(BuildArea.Pylon, []):
                distance = point.distance_to_point2(target_pos)
                if distance < best_distance:
                    best_distance = distance
                    best_point = point
            if best_point:
                self.temp2x2.insert(0, best_point)

        return
