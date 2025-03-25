from typing import Optional

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sharpy.plans.acts import GridBuilding


class Building(GridBuilding):
    def __init__(
        self,
        unit_type: UnitTypeId,
        to_count: int = 1,
        iterator: Optional[int] = None,
        priority: bool = False,
        allow_wall: bool = True,
    ):

        super().__init__(unit_type, to_count, iterator, priority, allow_wall)

    async def execute(self) -> bool:
        if (
            self.knowledge.enemy_race == Race.Zerg
            and (self.unit_type == UnitTypeId.PYLON or self.unit_type == UnitTypeId.GATEWAY)
            and self.knowledge.reserved_minerals == 0
            and self.to_count == 1
        ):
            self.consider_worker_production = True
        else:
            self.consider_worker_production = False
        return await super().execute()
