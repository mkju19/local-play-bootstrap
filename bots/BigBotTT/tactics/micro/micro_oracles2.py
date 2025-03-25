from typing import Dict
from sharpy.combat import MicroStep, Action, MoveType
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.unit import Unit
from sc2.units import Units
from sharpy.managers.core import UnitValue

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


class MicroOracles2(MicroStep):
    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if isinstance(current_command.target, Unit):
            target_pos = current_command.target.position
        else:
            target_pos = current_command.target

        if self.move_type == MoveType.PanicRetreat or self.move_type == MoveType.DefensiveRetreat:
            if unit.has_buff(BuffId.ORACLEWEAPON):
                return Action(None, False, AbilityId.BEHAVIOR_PULSARBEAMOFF)
            target = self.pather.find_influence_air_path(unit.position, target_pos)
            return Action(target, False)

        if self.move_type == MoveType.Harass:
            target_action = self.focus_fire(unit, current_command, high_priority_worker)
            if target_action.is_attack and isinstance(target_action.target, Unit):
                target_unit: Unit = target_action.target
                if target_unit.type_id in UnitValue.worker_types:
                    if self.ready_to_shoot(unit):
                        return self.activate_attack(unit, target_action)
                    else:
                        target_pos = self.pather.find_weak_influence_air(unit.position, 4.5)
                        target = self.pather.find_influence_air_path(unit.position, target_pos)
                        return Action(target, False)
                # elif not target_unit.is_structure:

            targets = self.cache.enemy(self.unit_values.enemy_worker_type)
            if targets:
                close_to_me = targets.closer_than(8, unit.position)
                close_to_target = targets.closer_than(10, target_pos)
                if close_to_me:
                    targets = close_to_me
                elif close_to_target:
                    targets = close_to_target
        else:
            targets = self.cache.enemy_in_range(unit.position, 10).filter(lambda u: u.is_light and not u.is_flying)

        if targets:
            closest = targets.closest_to(unit)
            distance = closest.distance_to(unit)

            if distance > 40 and unit.has_buff(BuffId.ORACLEWEAPON):
                return Action(None, False, AbilityId.BEHAVIOR_PULSARBEAMOFF)
            if distance < 5:
                if not unit.has_buff(BuffId.ORACLEWEAPON):
                    if unit.energy > 40:
                        return Action(None, False, AbilityId.BEHAVIOR_PULSARBEAMON)
                    else:
                        target = self.pather.find_weak_influence_air(unit.position, 10)
                        return Action(target, False)
                else:
                    self.convert_to_attack(unit, Action(closest, True))

            target = self.pather.find_weak_influence_air(closest.position, 10)
            target = self.pather.find_influence_air_path(unit.position, target)
            return Action(target, False)

        target = self.pather.find_influence_air_path(unit.position, target_pos)

        return self.deactivate_attack(unit, Action(target, False))

    def activate_attack(self, unit: Unit, attack_command: Action) -> Action:
        if isinstance(attack_command.target, Unit):
            if unit.distance_to(attack_command.target) > 6:
                return attack_command

        if not unit.has_buff(BuffId.ORACLEWEAPON):
            return Action(None, False, AbilityId.BEHAVIOR_PULSARBEAMON)
        return attack_command

    def deactivate_attack(self, unit: Unit, move_command: Action) -> Action:
        if unit.has_buff(BuffId.ORACLEWEAPON):
            return Action(None, False, AbilityId.BEHAVIOR_PULSARBEAMOFF)
        return move_command

    def convert_to_attack(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type == MoveType.Harass:
            target_action = self.focus_fire(unit, current_command, high_priority_worker)
        else:
            target_action = self.focus_fire(unit, current_command, high_priority)

        if target_action.is_attack and isinstance(target_action.target, Unit):
            target_unit: Unit = target_action.target
            if target_unit.distance_to(unit) < 5 and not target_unit.is_structure:
                if self.ready_to_shoot(unit):
                    return self.activate_attack(unit, target_action)
                else:
                    target_pos = self.pather.find_weak_influence_air(unit.position, 4.5)
                    target = self.pather.find_influence_air_path(unit.position, target_pos)
                    return Action(target, False)

        # noinspection PyTypeChecker
        target_pos = self.pather.find_weak_influence_air(unit.position, 4.5)
        target = self.pather.find_influence_air_path(unit.position, target_pos)

        return Action(target, False)
