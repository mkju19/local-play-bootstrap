from sc2.ids.ability_id import AbilityId
from sharpy.combat import GenericMicro, Action

from sc2.unit import Unit
from sharpy.interfaces.combat_manager import MoveType


class MicroRoaches(GenericMicro):
    """
    Basic micro for Roaches that uses burrow.

    todo: take advantage of possible UpgradeId.TUNNELINGCLAWS and move while burrowed.
    todo: maybe unburrow when under
        * EffectId.SCANNERSWEEP,
        * EffectId.PSISTORMPERSISTENT,
        * revealed by raven/observer/overseer, etc.
    """

    def __init__(self, knowledge: "Knowledge"):
        super().__init__(knowledge)
        self.burrow_up_percentage = 0.9
        self.burrow_down_percentage = 0.5

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        burrow_ready = self.cd_manager.is_ready(unit.tag, AbilityId.BURROWDOWN_ROACH)
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command

        if unit.is_burrowed and unit.health_percentage > self.burrow_up_percentage:
            return Action(None, False, AbilityId.BURROWUP_ROACH)
        
        if not unit.is_burrowed and unit.health_percentage < self.burrow_down_percentage and burrow_ready:
            return Action(None, False, AbilityId.BURROWDOWN_ROACH)   
        
        if unit.is_burrowed and self.cd_manager.is_ready(unit.tag, AbilityId.BURROWDOWN_ROACH):
            zones = self.zone_manager.our_zones_with_minerals
            if zones:
                position = zones[0].behind_mineral_position_center
                self.cd_manager.used_ability(unit.tag, AbilityId.MOVE_MOVE)
                return Action(position, False, AbilityId.MOVE_MOVE)

        if not self.cd_manager.is_ready(unit.tag, AbilityId.MOVE_MOVE) and unit.health_percentage < 0.9:
                return Action(unit.position, False)

        return super().unit_solve_combat(unit, current_command)