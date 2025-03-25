from typing import Optional

from sharpy.general.extended_ramp import ExtendedRamp, RampPosition
from sharpy.general.zone import Zone
from sharpy.plans.acts import BuildPosition
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.units import Units

ADEPT_STARTS = 2 * 60 + 30


class BlockMain(BuildPosition):
    def __init__(self, hold_probe: bool = False, reserve_minerals: int = 0, finish_pylon=False):
        self.reserve_minerals = reserve_minerals
        self.hold_probe = hold_probe
        self.completed = False
        self.created_once = False
        self.center: Point2 = Point2((0, 0))
        self.danger = False
        self.finish_pylon = finish_pylon
        self.estimated_arrival = ADEPT_STARTS
        super().__init__(UnitTypeId.PYLON, None, True, False)

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        ramp: Optional[ExtendedRamp] = self.zone_manager.expansion_zones[0].ramp
        if ramp:
            self.position = ramp.positions.get(RampPosition.PylonBlockVsProtoss, None)
            natural: Zone = self.zone_manager.expansion_zones[1]
            self.center = natural.center_location
        else:
            self.position = None
        # Adept speed is 3.5, let's estimate travel speed to be slightly faster with shades

    async def execute(self) -> bool:
        if not self.position or self.knowledge.enemy_race != Race.Protoss or self.ai.time < self.estimated_arrival:
            return True

        if self.estimated_arrival <= ADEPT_STARTS:
            enemy_main_index = self.zone_manager.expansion_zones[-1].zone_index
            self.estimated_arrival = (
                ADEPT_STARTS + 22 + self.zone_manager.expansion_zones[1].paths[enemy_main_index].distance / 4.5
            )

        pylons: Units = self.cache.own_in_range(self.position, 1).of_type(UnitTypeId.PYLON)
        if pylons:
            self.created_once = True
            pylon = pylons[0]
            if self.finish_pylon:
                # No cancel logic
                self.completed = True
                return True

            if pylon.build_progress > 0.95:
                pylon(AbilityId.CANCEL_BUILDINPROGRESS)
                self.completed = True
                return True

        if self.created_once:
            return True

        enemies = self.cache.enemy_in_range(self.center, 35)
        adept_danger = enemies.of_type({UnitTypeId.ADEPT, UnitTypeId.ADEPTPHASESHIFT})

        if len(adept_danger) > 1 and len(adept_danger) + 1 >= len(enemies):
            self.danger = True  # Probably an adept dive

        if self.danger:
            return await super().execute()

        if self.hold_probe:
            worker = self.get_worker_builder(self.center, self.builder_tag)
            if worker:
                self.set_worker(worker)
                worker.move(self.center.towards(self.ai.start_location, 1))

        if self.reserve_minerals > 0:
            self.knowledge.reserve(self.reserve_minerals, 0)
        return True
