from typing import Dict, Optional

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit, UnitOrder
from sharpy.managers.core import ManagerBase


class ExtendedUnitManager(ManagerBase):
    def __init__(self) -> None:
        super().__init__()
        self._is_repairing_dict: Dict[int, int] = {}
        self._is_building_dict: Dict[int, int] = {}

    async def update(self):
        if self.knowledge.enemy_race == Race.Terran:
            self._terran_building_check()

    async def post_update(self):
        pass

    def is_repairing(self, unit: Unit) -> Optional[Unit]:
        tag = self._is_repairing_dict.get(unit.tag, None)
        if tag:
            return self.cache.by_tag(tag)
        return None

    def is_building(self, unit: Unit) -> Optional[Unit]:
        tag = self._is_building_dict.get(unit.tag, None)
        if tag:
            return self.cache.by_tag(tag)
        return None

    def _terran_building_check(self):
        self._is_repairing_dict.clear()
        self._is_building_dict.clear()

        for scv in self.cache.enemy(UnitTypeId.SCV).filter(self.attackable):
            # Only visible scv
            units = self.cache.enemy_in_range(scv.position, 3.5, True)
            for unit in units:
                if unit.is_structure and unit.build_progress < 1:
                    # is the scv building this?
                    if scv.distance_to(unit) < unit.radius + 1:
                        self._is_building_dict[scv.tag] = unit.tag
                        break
                elif (
                    (unit.is_mechanical or unit.is_structure)
                    and unit.health_percentage < 1
                    and scv.is_facing(unit)
                    and unit.type_id != UnitTypeId.SCV
                ):
                    if scv.distance_to(unit) < unit.radius + 0.2 + scv.radius:
                        self._is_repairing_dict[scv.tag] = unit.tag
                        break

    def attackable(self, unit: Unit):
        return unit.can_be_attacked and not unit.is_memory and not unit.is_snapshot
