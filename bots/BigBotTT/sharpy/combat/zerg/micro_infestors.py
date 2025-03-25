from typing import Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.units import Units
from sharpy.combat import MicroStep, Action, MoveType
from sc2.unit import Unit


class MicroInfestors(MicroStep):
    def __init__(self):
        super().__init__()
        self.aoe_available = 0
        self.unburrow_distance = 10
        self.burrow_distance = 20
        self.requested_mode = AbilityId.BURROWUP_INFESTOR
        self.closest_enemy = 50

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        relevant_enemies = self.enemies_near_by.visible
        # unburrow if retreating
        if self.move_type == MoveType.PanicRetreat:
            if unit.type_id == UnitTypeId.INFESTORBURROWED and not relevant_enemies.exists:
                self.requested_mode = AbilityId.BURROWUP_INFESTOR
        # getting distance to closest enemy
        else:
            if relevant_enemies.exists:
                self.closest_enemy = relevant_enemies.closest_distance_to(unit)
            else:
                self.closest_enemy = 50
        # toggle mode request
        if self.closest_enemy <= self.burrow_distance:
            if self.requested_mode == AbilityId.BURROWUP_INFESTOR:
                self.requested_mode = AbilityId.BURROWDOWN_INFESTOR

        elif self.closest_enemy >= self.unburrow_distance:
            if self.requested_mode == AbilityId.BURROWDOWN_INFESTOR:
                self.requested_mode = AbilityId.BURROWUP_INFESTOR

        if unit.type_id == UnitTypeId.INFESTORBURROWED and self.requested_mode == AbilityId.BURROWUP_INFESTOR:
            return Action(None, False, self.requested_mode)
        elif unit.type_id == UnitTypeId.INFESTOR and self.requested_mode == AbilityId.BURROWDOWN_INFESTOR:
            return Action(None, False, self.requested_mode)

        closest = self.closest_units.get(unit.tag)
        if not closest or closest.distance_to(unit) > 14:
            # not in combat, follow the army
            return current_command

        if unit.energy < 75:
            focus = self.group.center
            best_position = self.pather.find_weak_influence_ground(focus, 6)
            return Action(best_position, False)

        if self.cd_manager.is_ready(unit.tag, AbilityId.NEURALPARASITE_NEURALPARASITE):
            shuffler = unit.tag % 10
            best_score = 300
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 1 and not enemy.has_buff(BuffId.NEURALPARASITE):
                    score = enemy.health + self.unit_values.power(enemy) * 50
                    # TODO: Needs proper target locking in order to not fire at the same target
                    # Simple and stupid way in an attempt to not use ability on same target:
                    score += enemy.tag % (shuffler + 2)

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                return Action(target, False, AbilityId.NEURALPARASITE_NEURALPARASITE)

        if (
            self.aoe_available < self.ai.time
            and self.cd_manager.is_ready(unit.tag, AbilityId.FUNGALGROWTH_FUNGALGROWTH)
            and self.engaged_power.power > 4
        ):
            best_score = 2
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 0.5 and not enemy.has_buff(BuffId.FUNGALGROWTH):
                    score = self.cache.enemy_in_range(enemy.position, 2).amount

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                self.aoe_available = self.ai.time + 2
                return Action(target.position, False, AbilityId.FUNGALGROWTH_FUNGALGROWTH)

        return self.stay_safe(unit, current_command)

    def stay_safe(self, unit: Unit, current_command: Action) -> Action:
        """Partial retreat, micro back."""
        pos = self.pather.find_weak_influence_ground(unit.position, 3)
        return Action(pos, False)
