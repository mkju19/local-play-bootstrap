from typing import Dict

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.units import Units
from sharpy.combat import GenericMicro, Action

from sc2.unit import Unit
from sharpy.interfaces.combat_manager import MoveType

high_priority: Dict[UnitTypeId, int] = {
    # Terran
    UnitTypeId.SIEGETANK: 8,
    UnitTypeId.SIEGETANKSIEGED: 10,  # sieged tanks are much higher priority than unsieged
    UnitTypeId.WIDOWMINE: 8,
    UnitTypeId.WIDOWMINEBURROWED: 10,
    UnitTypeId.MULE: 3,
    UnitTypeId.SCV: 10,  # prioritize scv because they'll continue repairing otherwise
    UnitTypeId.GHOST: 7,
    UnitTypeId.REAPER: 4,
    UnitTypeId.MARAUDER: 4,
    UnitTypeId.MARINE: 3,
    UnitTypeId.CYCLONE: 6,
    UnitTypeId.HELLION: 5,
    UnitTypeId.HELLIONTANK: 5,
    UnitTypeId.THOR: 7,
    UnitTypeId.MEDIVAC: 8,
    UnitTypeId.VIKINGFIGHTER: 8,
    UnitTypeId.VIKINGASSAULT: 8,
    UnitTypeId.LIBERATORAG: 9,
    UnitTypeId.LIBERATOR: 8,
    UnitTypeId.RAVEN: 10,
    UnitTypeId.BATTLECRUISER: 8,
    UnitTypeId.MISSILETURRET: 1,
    UnitTypeId.BUNKER: 2,
    # Zerg
    UnitTypeId.DRONE: 4,
    UnitTypeId.ZERGLING: 5,
    UnitTypeId.BANELING: 7,
    UnitTypeId.BANELINGCOCOON: 7,
    UnitTypeId.ULTRALISK: 4,
    UnitTypeId.QUEEN: 5,
    UnitTypeId.ROACH: 6,
    UnitTypeId.RAVAGER: 8,
    UnitTypeId.RAVAGERCOCOON: 8,
    UnitTypeId.HYDRALISK: 7,
    UnitTypeId.HYDRALISKBURROWED: 7,
    UnitTypeId.LURKERMP: 9,
    UnitTypeId.LURKERMPEGG: 9,
    UnitTypeId.LURKERMPBURROWED: 9,
    UnitTypeId.INFESTOR: 10,
    UnitTypeId.BROODLORD: 10,
    UnitTypeId.BROODLORDCOCOON: 10,
    UnitTypeId.MUTALISK: 8,
    UnitTypeId.CORRUPTOR: 4,
    UnitTypeId.LARVA: -1,
    UnitTypeId.EGG: -1,
    UnitTypeId.LOCUSTMP: -1,
    # Protoss
    UnitTypeId.SENTRY: 8,
    UnitTypeId.HIGHTEMPLAR: 10,
    UnitTypeId.DARKTEMPLAR: 9,
    UnitTypeId.ADEPT: 4,
    UnitTypeId.ZEALOT: 4,
    UnitTypeId.STALKER: 5,
    UnitTypeId.IMMORTAL: 9,
    UnitTypeId.COLOSSUS: 10,
    UnitTypeId.ARCHON: 6,
    UnitTypeId.SHIELDBATTERY: 4,
    UnitTypeId.PHOTONCANNON: 4,
    UnitTypeId.PYLON: 2,
    UnitTypeId.CARRIER: 8,
    UnitTypeId.INTERCEPTOR: 2,
}

class MicroHydra(GenericMicro):
    def __init__(self):
        super().__init__()
        self.prio_dict = high_priority

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        """Have all units execute the current command."""
        return current_command
    
    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command
