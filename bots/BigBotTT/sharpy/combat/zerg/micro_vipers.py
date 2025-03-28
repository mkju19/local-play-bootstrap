from typing import Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.units import Units
from sharpy.combat import MicroStep, Action, MoveType
from sc2.unit import Unit


class MicroVipers(MicroStep):
    def __init__(self):
        super().__init__()
        self.blind_available = 0
        self.parasitic_bomb_available = 0

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command

        if unit.energy < 50:
            focus = self.group.center
            best_position = self.pather.find_weak_influence_air(focus, 6)
            return Action(best_position, False)

        if self.cd_manager.is_ready(unit.tag, AbilityId.EFFECT_ABDUCT):
            shuffler = unit.tag % 10
            best_score = 300
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 1 and enemy.can_be_attacked:
                    score = enemy.health + self.unit_values.power(enemy) * 50
                    # TODO: Needs proper target locking in order to not fire at the same target
                    # Simple and stupid way in an attempt to not use ability on same target:
                    score += enemy.tag % (shuffler + 2)

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                return Action(target, False, AbilityId.EFFECT_ABDUCT)

        if (
            self.parasitic_bomb_available < self.ai.time
            and self.cd_manager.is_ready(unit.tag, AbilityId.PARASITICBOMB_PARASITICBOMB)
            and self.engaged_power.power > 10
        ):
            best_score = 4
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by.filter(lambda u: u.type_id == UnitTypeId.COLOSSUS or u.is_flying):
                d = enemy.distance_to(unit)
                if d < 8 and self.unit_values.power(enemy) > 1 and not enemy.has_buff(BuffId.PARASITICBOMB):
                    score = self.cache.enemy_in_range(enemy.position, 3).flying.amount
                    # TODO: Needs proper target locking in order to not fire at the same target
                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                self.parasitic_bomb_available = self.ai.time + 3
                return Action(target, False, AbilityId.PARASITICBOMB_PARASITICBOMB)

        if (
            self.blind_available < self.ai.time
            and self.cd_manager.is_ready(unit.tag, AbilityId.BLINDINGCLOUD_BLINDINGCLOUD)
            and self.engaged_power.power > 10
        ):
            best_score = 5
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by.filter(
                lambda u: not u.is_flying and self.unit_values.ground_range(u) > 2
            ):
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 1 and not enemy.has_buff(BuffId.BLINDINGCLOUD):
                    score = (
                        self.cache.enemy_in_range(enemy.position, 5)
                        .filter(lambda u: not u.is_flying and self.unit_values.ground_range(u) > 2)
                        .amount
                    )
                    # TODO: Needs proper target locking in order to not fire at the same target
                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                self.blind_available = self.ai.time + 1
                return Action(target.position, False, AbilityId.BLINDINGCLOUD_BLINDINGCLOUD)

        return current_command

    def should_shoot(self):
        tick = self.ai.state.game_loop % 24
        return tick < 8

    def stay_safe(self, unit: Unit, current_command: Action) -> Action:
        """Partial retreat, micro back."""
        pos = self.pather.find_weak_influence_ground(unit.position, 5)
        return Action(pos, False)