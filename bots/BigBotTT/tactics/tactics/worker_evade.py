from sc2 import UnitTypeId, Race
from sc2.game_state import EffectData
from sc2.ids.effect_id import EffectId
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2pathlib import MapType
from sharpy.interfaces import IZoneManager
from sharpy.managers.core import PreviousUnitsManager
from sharpy.managers.core.roles import UnitTask
from sharpy.plans.acts import ActBase
from typing import TYPE_CHECKING, Dict, Optional, List, Tuple

if TYPE_CHECKING:
    from harvester_protoss.harvester_protoss import ProtossHarvester


class WorkerEvade(ActBase):
    ai: "ProtossHarvester"
    zone_manager: IZoneManager
    previous_units_manager: PreviousUnitsManager
    mine_map: Dict[int, int]

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.mine_map = {}
        self.previous_units_manager = knowledge.get_required_manager(PreviousUnitsManager)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)

    async def execute(self) -> bool:
        if self.ai.build_detector.worker_rush_detected:
            if self.ai.supply_workers < 3 and self.ai.supply_army > 1:
                # Evade with everything!
                for probe in self.cache.own(UnitTypeId.PROBE):
                    await self.evade_probe(probe)
                    self.roles.set_task(UnitTask.Reserved, probe)

            for probe in self.roles.get_types_from({UnitTypeId.PROBE}, UnitTask.Gathering):  # type: Unit
                if probe.shield + probe.health < 10:
                    await self.evade_probe(probe)
                    self.roles.set_task(UnitTask.Gathering, probe)
        elif self.ai.enemy_race == Race.Terran:
            self.widow_mine_dodge()
            self.liberator_dodge()
        elif self.ai.enemy_race == Race.Protoss:
            self.stasis_mine_dodge()
            self.storm_dodge()
        return True  # Never block

    def storm_dodge(self):
        lib_zones: List[Tuple[Point2, EffectData]] = self.cache.effects(EffectId.PSISTORMPERSISTENT)

        for pos, effect_data in lib_zones:
            own = self.cache.own_in_range(pos, effect_data.radius + 1.5)
            workers = own(UnitTypeId.PROBE)
            for worker in workers:
                self.generic_evade(worker)

    def stasis_mine_dodge(self):
        self.clear_mine_keys()

        for our_zone in self.zone_manager.our_zones:
            for mine in our_zone.known_enemy_units(UnitTypeId.ORACLESTASISTRAP):
                if mine.buff_duration_remain == 0:
                    workers = self.cache.own_in_range(mine.position, 6.5).of_type(UnitTypeId.PROBE)
                    if len(workers) > 1:
                        # take closest worker and evade with others
                        tag = self.mine_map.get(mine.tag)
                        closest: Optional[Unit] = None

                        if tag:
                            closest = workers.find_by_tag(tag)

                        if closest is None:
                            closest = workers.closest_to(mine)
                            self.mine_map[mine.tag] = closest.tag

                        workers.remove(closest)

                        for worker in workers:
                            self.generic_evade(worker)

    def liberator_dodge(self):
        lib_zones: List[Tuple[Point2, EffectData]] = []
        lib_zones.extend(self.cache.effects(EffectId.LIBERATORTARGETMORPHDELAYPERSISTENT))
        lib_zones.extend(self.cache.effects(EffectId.LIBERATORTARGETMORPHPERSISTENT))

        for pos, effect_data in lib_zones:
            own = self.cache.own_in_range(pos, effect_data.radius + 1.5)
            workers = own(UnitTypeId.PROBE)
            for worker in workers:
                self.generic_evade(worker)

    def widow_mine_dodge(self):
        self.clear_mine_keys()

        for our_zone in self.zone_manager.our_zones:
            for mine in our_zone.known_enemy_units(UnitTypeId.WIDOWMINEBURROWED):
                if mine.buff_duration_remain == 0:
                    workers = self.cache.own_in_range(mine.position, 8).of_type(UnitTypeId.PROBE)
                    if len(workers) > 1:
                        # take closest worker and evade with others
                        tag = self.mine_map.get(mine.tag)
                        closest: Optional[Unit] = None

                        if tag:
                            closest = workers.find_by_tag(tag)

                        if closest is None:
                            closest = workers.closest_to(mine)
                            self.mine_map[mine.tag] = closest.tag

                        workers.remove(closest)

                        for worker in workers:
                            self.generic_evade(worker)

    def clear_mine_keys(self):
        clear_keys = []
        for key_tag in self.mine_map.keys():
            unit = self.cache.by_tag(key_tag)
            if unit is None or unit.type_id not in {UnitTypeId.WIDOWMINEBURROWED, UnitTypeId.ORACLESTASISTRAP}:
                clear_keys.append(key_tag)
        for key_tag in clear_keys:
            self.mine_map.pop(key_tag)

    def generic_evade(self, worker: Unit):
        # safe_spot = self.ai.start_location.towards(
        #     self.zone_manager.expansion_zones[0].behind_mineral_position_center, -5
        # )
        # safe_spot = Point2(self.pather.map.find_low_inside_walk(MapType.Ground, worker.position, mine.position, 8)[0])
        safe_spot = Point2(self.pather.map.safest_spot(MapType.Ground, worker.position, 5)[0])
        # self.client.debug_line_out(worker.position3d, Point3((safe_spot.x, safe_spot.y, worker.position3d.z)))

        worker.move(safe_spot)
        self.roles.set_task(UnitTask.Reserved, worker)

    async def evade_probe(self, probe):
        safe_spot = Point2(self.pather.map.safest_spot(MapType.Ground, probe.position, 5)[0])
        if safe_spot.distance_to(probe.position) > 2:
            probe.move(safe_spot)
