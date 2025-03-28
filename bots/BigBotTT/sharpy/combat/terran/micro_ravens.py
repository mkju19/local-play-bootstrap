from typing import Optional

from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.units import Units
from sharpy.combat import MicroStep, Action, MoveType
from sc2.unit import Unit


class MicroRavens(MicroStep):
    def __init__(self):
        super().__init__()
        self.anti_armor_available = 0

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.PanicRetreat, MoveType.DefensiveRetreat}:
            return current_command
        
        bc = unit
        health_to_jump = 100
        if self.engaged_power.air_power > 8:
            health_to_jump = 120

        if bc.health < health_to_jump and self.cd_manager.is_ready(bc.tag, AbilityId.MOVE_MOVE):
            zones = self.zone_manager.our_zones_with_minerals
            if zones:
                position = zones[0].behind_mineral_position_center
                self.cd_manager.used_ability(bc.tag, AbilityId.MOVE_MOVE)
                return Action(position, False, AbilityId.MOVE_MOVE)

        if not self.cd_manager.is_ready(bc.tag, AbilityId.MOVE_MOVE) and bc.health_percentage < 0.9:
            scvs: Units = self.knowledge.unit_cache.own(UnitTypeId.SCV)
            if len(scvs) > 10 and scvs.closest_distance_to(bc) < 20:
                # Stay put!
                return Action(bc.position, True)
            
        if unit.energy < 50:
            focus = self.group.center
            best_position = self.pather.find_weak_influence_air(focus, 6)
            return Action(best_position, False)

        if self.cd_manager.is_ready(unit.tag, AbilityId.EFFECT_INTERFERENCEMATRIX):
            shuffler = unit.tag % 10
            best_score = 300
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 1 and not enemy.has_buff(BuffId.RAVENSCRAMBLERMISSILE):
                    score = enemy.health + self.unit_values.power(enemy) * 50
                    # TODO: Needs proper target locking in order to not fire at the same target
                    # Simple and stupid way in an attempt to not use ability on same target:
                    score += enemy.tag % (shuffler + 2)

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                return Action(target, False, AbilityId.EFFECT_INTERFERENCEMATRIX)

        if (
            self.anti_armor_available < self.ai.time
            and self.cd_manager.is_ready(unit.tag, AbilityId.EFFECT_ANTIARMORMISSILE)
            and self.engaged_power.power > 10
        ):
            best_score = 5
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if (
                    d < 11
                    and self.unit_values.power(enemy) > 1
                    and not enemy.has_buff(BuffId.RAVENSHREDDERMISSILEARMORREDUCTION)
                ):
                    score = self.cache.enemy_in_range(enemy.position, 5).amount

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                self.anti_armor_available = self.ai.time + 3
                return Action(target, False, AbilityId.EFFECT_ANTIARMORMISSILE)

        return current_command

    def should_shoot(self):
        tick = self.ai.state.game_loop % 24
        return tick < 8
