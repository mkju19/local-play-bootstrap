from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit
from sharpy.managers.core import ManagerBase


class StateAnalyzer(ManagerBase):
    def __init__(self) -> None:
        self.natural_expansion_blocked: bool = False
        self.natural_siege: bool = False
        self.natural_siege_ready: bool = False
        self.cannon_rush: bool = False
        self.cannon_contain: bool = False
        self.cannon_ready: bool = False

        self.siege_buildings = {
            UnitTypeId.BUNKER,
            UnitTypeId.PLANETARYFORTRESS,
            UnitTypeId.SHIELDBATTERY,
            UnitTypeId.SPINECRAWLER,
        }

        super().__init__()

    async def update(self):
        self.reset()
        main = self.zone_manager.expansion_zones[0]
        natural = self.zone_manager.expansion_zones[1]
        enemy_buildings_main = main.known_enemy_units.structure
        enemy_buildings_nat = natural.known_enemy_units.structure

        for building in enemy_buildings_main:  # type: Unit
            if building.type_id == UnitTypeId.PHOTONCANNON:
                self.cannon_rush = True
                if building.is_ready:
                    self.cannon_ready = True

        if enemy_buildings_nat:
            for building in enemy_buildings_nat:  # type: Unit
                if building.type_id == UnitTypeId.PHOTONCANNON:
                    self.cannon_contain = True
                    self.natural_siege = True

                    if building.is_ready:
                        self.natural_siege_ready = True
                        self.cannon_ready = True

                if building.type_id in self.siege_buildings:
                    self.natural_siege = True
                    if building.is_ready:
                        self.natural_siege_ready = True

                if building.distance_to(natural.center_location) < building.radius + 3:
                    # Not 100% accurate, but should be close enough
                    self.natural_expansion_blocked = True

    def reset(self):
        self.natural_expansion_blocked = False
        self.natural_siege = False
        self.cannon_rush = False
        self.cannon_contain = False
        self.cannon_ready = False

    async def post_update(self):
        ...
        # if self.debug:
