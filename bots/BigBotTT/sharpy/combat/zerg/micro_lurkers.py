from typing import Optional, Dict

from sharpy.combat import Action, MoveType, GenericMicro
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit

class MicroLurkers(GenericMicro):
    def __init__(self):
        super().__init__()
        self.unburrow_distance = 15
        self.burrow_distance = 7
        self.requested_mode = AbilityId.BURROWUP_LURKER
        self.closest_enemy = 50

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        relevant_enemies = self.enemies_near_by.visible
        # unburrow if retreating
        if self.move_type == MoveType.PanicRetreat:
            if unit.type_id == UnitTypeId.LURKERMPBURROWED and not relevant_enemies.exists:
                self.requested_mode = AbilityId.BURROWUP_LURKER
        # getting distance to closest enemy
        else:
            if relevant_enemies.exists:
                self.closest_enemy = relevant_enemies.closest_distance_to(unit)
            else:
                self.closest_enemy = 50
        # toggle mode request
        if self.closest_enemy <= self.burrow_distance:
            if self.requested_mode == AbilityId.BURROWUP_LURKER:
                self.requested_mode = AbilityId.BURROWDOWN_LURKER

        elif self.closest_enemy >= self.unburrow_distance:
            if self.requested_mode == AbilityId.BURROWDOWN_LURKER:
                self.requested_mode = AbilityId.BURROWUP_LURKER

        if unit.type_id == UnitTypeId.LURKERMPBURROWED and self.requested_mode == AbilityId.BURROWUP_LURKER:
            return Action(None, False, self.requested_mode)
        elif unit.type_id == UnitTypeId.LURKERMP and self.requested_mode == AbilityId.BURROWDOWN_LURKER:
            return Action(None, False, self.requested_mode)
        else:
            return current_command
