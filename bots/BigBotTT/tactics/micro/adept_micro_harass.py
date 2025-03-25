from typing import Dict, Optional, Callable

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.constants import ALL_GAS
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sharpy.combat import Action, MoveType
from sharpy.combat.default_micro_methods import changelings
from sharpy.combat.protoss import MicroAdepts
from tactics.micro.harvester_micro_methods import ignored_types

high_priority: Dict[UnitTypeId, int] = {
    # Terran
    UnitTypeId.MULE: 9,
    UnitTypeId.SCV: 9,
    UnitTypeId.SIEGETANK: 3,
    UnitTypeId.SIEGETANKSIEGED: 5,  # sieged tanks are much higher priority than unsieged
    UnitTypeId.GHOST: 10,
    UnitTypeId.REAPER: 8,
    UnitTypeId.MARAUDER: 4,
    UnitTypeId.MARINE: 8,
    UnitTypeId.CYCLONE: 4,
    UnitTypeId.HELLION: 8,
    UnitTypeId.HELLIONTANK: 3,
    UnitTypeId.THOR: 3,
    UnitTypeId.MEDIVAC: -1,
    UnitTypeId.VIKINGFIGHTER: -1,
    UnitTypeId.VIKINGASSAULT: -1,
    UnitTypeId.LIBERATORAG: -1,
    UnitTypeId.LIBERATOR: -1,
    UnitTypeId.RAVEN: -1,
    UnitTypeId.BATTLECRUISER: -1,
    UnitTypeId.MISSILETURRET: 1,
    UnitTypeId.BUNKER: 2,
    # Zerg
    UnitTypeId.DRONE: 9,
    UnitTypeId.ZERGLING: 8,
    UnitTypeId.BANELING: 10,
    UnitTypeId.ULTRALISK: 4,
    UnitTypeId.QUEEN: 6,
    UnitTypeId.ROACH: 4,
    UnitTypeId.RAVAGER: 4,
    UnitTypeId.HYDRALISK: 8,
    UnitTypeId.HYDRALISKBURROWED: 8,
    UnitTypeId.LURKERMP: 3,
    UnitTypeId.LURKERMPBURROWED: 3,
    UnitTypeId.INFESTOR: 10,
    UnitTypeId.BROODLORD: -1,
    UnitTypeId.MUTALISK: -1,
    UnitTypeId.CORRUPTOR: -1,
    UnitTypeId.INFESTEDTERRAN: 1,
    UnitTypeId.LARVA: -1,
    UnitTypeId.EGG: -1,
    UnitTypeId.LOCUSTMP: -1,
    # Protoss
    UnitTypeId.SENTRY: 9,
    UnitTypeId.PROBE: 10,
    UnitTypeId.HIGHTEMPLAR: 10,
    UnitTypeId.DARKTEMPLAR: 9,
    UnitTypeId.ADEPT: 8,
    UnitTypeId.ZEALOT: 8,
    UnitTypeId.STALKER: 4,
    UnitTypeId.IMMORTAL: 2,
    UnitTypeId.COLOSSUS: 3,
    UnitTypeId.ARCHON: 4,
    UnitTypeId.SHIELDBATTERY: 1,
    UnitTypeId.PHOTONCANNON: 1,
    UnitTypeId.PYLON: 0,
    UnitTypeId.FLEETBEACON: 0,
}

high_priority_worker: Dict[UnitTypeId, int] = {
    # Terran
    UnitTypeId.MULE: 10,
    UnitTypeId.SCV: 10,
    UnitTypeId.SIEGETANK: 1,
    UnitTypeId.SIEGETANKSIEGED: 1,  # sieged tanks are much higher priority than unsieged
    UnitTypeId.GHOST: 5,
    UnitTypeId.REAPER: 2,
    UnitTypeId.MARAUDER: 1,
    UnitTypeId.MARINE: 2,
    UnitTypeId.CYCLONE: 1,
    UnitTypeId.HELLION: 2,
    UnitTypeId.HELLIONTANK: 1,
    UnitTypeId.THOR: 0,
    UnitTypeId.MEDIVAC: -1,
    UnitTypeId.VIKINGFIGHTER: -1,
    UnitTypeId.VIKINGASSAULT: -1,
    UnitTypeId.LIBERATORAG: -1,
    UnitTypeId.LIBERATOR: -1,
    UnitTypeId.RAVEN: -1,
    UnitTypeId.BATTLECRUISER: -1,
    UnitTypeId.MISSILETURRET: 0,
    UnitTypeId.BUNKER: 0,
    # Zerg
    UnitTypeId.DRONE: 10,
    UnitTypeId.ZERGLING: 1,
    UnitTypeId.BANELING: 2,
    UnitTypeId.ULTRALISK: 1,
    UnitTypeId.QUEEN: 1,
    UnitTypeId.ROACH: 1,
    UnitTypeId.RAVAGER: 1,
    UnitTypeId.HYDRALISK: 2,
    UnitTypeId.HYDRALISKBURROWED: 8,
    UnitTypeId.LURKERMP: 1,
    UnitTypeId.LURKERMPBURROWED: 1,
    UnitTypeId.INFESTOR: 2,
    UnitTypeId.BROODLORD: -1,
    UnitTypeId.MUTALISK: -1,
    UnitTypeId.CORRUPTOR: -1,
    UnitTypeId.INFESTEDTERRAN: 1,
    UnitTypeId.LARVA: -1,
    UnitTypeId.EGG: -1,
    UnitTypeId.LOCUSTMP: -1,
    # Protoss
    UnitTypeId.SENTRY: 9,
    UnitTypeId.PROBE: 10,
    UnitTypeId.HIGHTEMPLAR: 5,
    UnitTypeId.DARKTEMPLAR: 2,
    UnitTypeId.ADEPT: 2,
    UnitTypeId.ZEALOT: 2,
    UnitTypeId.STALKER: 1,
    UnitTypeId.IMMORTAL: 0,
    UnitTypeId.COLOSSUS: 0,
    UnitTypeId.ARCHON: 1,
    UnitTypeId.SHIELDBATTERY: 0,
    UnitTypeId.PHOTONCANNON: 0,
    UnitTypeId.PYLON: 0,
    UnitTypeId.FLEETBEACON: 0,
}


class MicroAdeptsHarass(MicroAdepts):
    def __init__(self, micro_shades: bool = True):
        self.last_all_shoot = 0
        super().__init__(micro_shades)

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type == MoveType.Harass:
            if not current_command.is_attack:
                return current_command
            else:
                return self.convert_to_attack(unit, current_command)

        if self.move_type == MoveType.SearchAndDestroy and current_command.position:
            if self.cd_manager.is_ready(unit.tag, AbilityId.ADEPTPHASESHIFT_ADEPTPHASESHIFT):
                shuffler = unit.tag % 10
                target = self.get_target(self.enemies_near_by, current_command.position, unit, shuffler)
                if target is not None:
                    return Action(target.position, False, AbilityId.ADEPTPHASESHIFT_ADEPTPHASESHIFT)

        return super().unit_solve_combat(unit, current_command)

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        if self.move_type == MoveType.Harass:
            self.micro_shades = False
            all_shoot = True
            for unit in units:
                all_shoot &= self.ready_to_shoot(unit)
            if all_shoot:
                self.last_all_shoot = self.ai.time
            if not all_shoot and self.last_all_shoot > self.ai.time - 0.1:
                # Create a delay so that both units can finish shooting
                all_shoot = True

            workers = self.cache.enemy_workers.closer_than(20, self.center)
            if workers:
                if not all_shoot or not self.enemies_near_by.closer_than(6, self.center):
                    target = workers.closest_to(self.center)
                    pos = self.pather.find_low_inside_ground(self.center, target.position, 4)
                    return Action(pos, False)
        else:
            self.micro_shades = True

        return super().group_solve_combat(units, current_command)

    def convert_to_attack(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type == MoveType.Harass:
            target_action = self.focus_fire_harass(unit, current_command, high_priority_worker)
        else:
            target_action = self.focus_fire(unit, current_command, high_priority)

        if target_action.is_attack and isinstance(target_action.target, Unit):
            target_unit: Unit = target_action.target
            if target_unit.distance_to(unit) < 5 and not target_unit.is_structure:
                if self.ready_to_shoot(unit):
                    return target_action
                else:
                    target_pos = self.pather.find_weak_influence_ground(unit.position, 4.5)
                    target = self.pather.find_influence_ground_path(unit.position, target_pos)
                    return Action(target, False)

        if not self.enemies_near_by and unit.distance_to(self.original_target) > 20:
            return current_command

        # noinspection PyTypeChecker
        target_pos = self.pather.find_weak_influence_ground(self.group.center, 4.5)
        target = self.pather.find_influence_ground_path(unit.position, target_pos)

        return Action(target, False)

    def focus_fire_harass(self, unit: Unit, current_command: Action, prio: Optional[Dict[UnitTypeId, int]]) -> Action:
        shoot_air = self.unit_values.can_shoot_air(unit)
        shoot_ground = self.unit_values.can_shoot_ground(unit)

        lookup = self.min_range(unit) + 3
        enemies = self.cache.enemy_in_range(unit.position, lookup).not_structure

        last_target = self.last_targeted(unit)

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
                else 2 * self.unit_values.power_by_type(u.type_id, 1 - u.shield_health_percentage)
            )

        best_target: Optional[Unit] = None
        best_score: float = 0
        enemy_gas = self.cache.enemy(ALL_GAS)

        for enemy in enemies:  # type: Unit
            if enemy.type_id in ignored_types:
                continue

            if not self.is_target(enemy):
                continue

            if not shoot_air and enemy.is_flying:
                continue

            if not shoot_ground and not enemy.is_flying:
                continue

            pos: Point2 = enemy.position
            score = value_func(enemy) + (1 - pos.distance_to(unit) / lookup)
            if enemy.tag == last_target:
                score += 3

            if enemy.health < self.focus_fired.get(enemy.tag, 0) + unit.calculate_damage_vs_target(enemy)[0]:
                score *= 1.5

            if self.focus_fired.get(enemy.tag, 0) > enemy.health:
                score *= 0.1

            if enemy.type_id == self.unit_values.enemy_worker_type:
                if enemy_gas:
                    closest_gas = enemy_gas.closest_to(enemy)
                    if closest_gas.distance_to(enemy) < 4 and enemy.is_facing(closest_gas):
                        # Probably can't hit it anyway
                        score *= 0.1

            if score > best_score:
                best_target = enemy
                best_score = score

        if best_target:
            self.focus_fired[best_target.tag] = (
                self.focus_fired.get(best_target.tag, 0) + unit.calculate_damage_vs_target(best_target)[0]
            )

            return Action(best_target, True)

        return current_command
