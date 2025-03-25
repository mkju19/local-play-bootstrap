from typing import Optional, Dict, Callable

from managers import ExtendedUnitManager
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sharpy.combat import MicroStep, Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

ignored_types = {UnitTypeId.LARVA, UnitTypeId.EGG}

repair_danger = {UnitTypeId.PLANETARYFORTRESS, UnitTypeId.BUNKER}

changelings = {
    UnitTypeId.CHANGELING,
    UnitTypeId.CHANGELINGMARINE,
    UnitTypeId.CHANGELINGMARINESHIELD,
    UnitTypeId.CHANGELINGZEALOT,
    UnitTypeId.CHANGELINGZERGLING,
    UnitTypeId.CHANGELINGZERGLINGWINGS,
}


class HarvesterMicroMethods:
    @staticmethod
    def focus_fire(
        step: MicroStep, unit: Unit, current_command: Action, prio: Optional[Dict[UnitTypeId, int]]
    ) -> Action:
        unit_manager = step.knowledge.get_manager(ExtendedUnitManager)

        shoot_air = step.unit_values.can_shoot_air(unit)
        shoot_ground = step.unit_values.can_shoot_ground(unit)

        air_range = step.unit_values.air_range(unit)
        ground_range = step.unit_values.ground_range(unit)
        lookup = min(air_range + 3, ground_range + 3)
        enemies = step.cache.enemy_in_range(unit.position, lookup)

        last_target = step.last_targeted(unit)

        if not enemies:
            # No enemies to shoot at
            return current_command

        value_func: Callable[[Unit], float]
        if prio:
            value_func = (
                lambda u: 1 if u.type_id in changelings else prio.get(u.type_id, -1) * (1 - u.shield_health_percentage)
            )
        else:
            value_func = (
                lambda u: 1
                if u.type_id in changelings
                else 2 * step.unit_values.power_by_type(u.type_id, 300 / (100 + u.health + u.shield))
            )

        best_target: Optional[Unit] = None
        best_score: float = 0
        for enemy in enemies:  # type: Unit
            if enemy.type_id in ignored_types:
                continue

            if not step.is_target(enemy):
                continue

            if not shoot_air and enemy.is_flying:
                continue

            if not shoot_ground and not enemy.is_flying:
                continue

            pos: Point2 = enemy.position
            score = value_func(enemy) + (1 - pos.distance_to(unit) / lookup)
            if enemy.tag == last_target:
                score += 3

            repair_target = unit_manager.is_repairing(enemy)
            if repair_target:
                if repair_target.type_id in repair_danger:
                    score += 5
                else:
                    score *= 2

            if step.focus_fired.get(enemy.tag, 0) > enemy.health and score > 0:
                score *= 0.1

            if prio and enemy.is_structure and enemy.type_id not in prio:
                if step.unit_values.power(unit) == 0 or enemy.health > 700:
                    # try to not attack planetaries or other useless building when not needed
                    score -= 10

            if score > best_score:
                best_target = enemy
                best_score = score

        if best_target:
            step.focus_fired[best_target.tag] = (
                step.focus_fired.get(best_target.tag, 0) + unit.calculate_damage_vs_target(best_target)[0]
            )

            return Action(best_target, True)

        return current_command
