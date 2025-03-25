from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2pathlib.mappings import VisionStatus
from sharpy.combat import Action, MicroStep
from sc2.unit import Unit
from sc2.units import Units

has_detection = {UnitTypeId.RAVEN, UnitTypeId.OVERSEER, UnitTypeId.OBSERVER}


class MicroObservers2(MicroStep):
    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if isinstance(current_command.target, Unit):
            target_pos = current_command.target.position
        else:
            target_pos = current_command.target

        enemies = self.cache.enemy_in_range(unit.position, 15, False)
        if enemies:
            if enemies.of_type(has_detection):
                forward_d = 0
            else:
                forward_d = 4
        else:
            forward_d = 8

        target = self.pather.find_path(self.group.center, target_pos, forward_d)  # move ahead of group

        if target_pos.distance_to(target) < 5:
            target = self.group.center

        other_observers = self.cache.own(UnitTypeId.OBSERVER).tags_not_in([unit.tag])
        if other_observers:
            # Try to keep observers separated from each other
            closest = other_observers.closest_to(unit)
            if closest.distance_to(unit) < 5:
                pos: Point2 = closest.position
                target = unit.position.towards(pos, -6)

        # for enemy in enemies:  # type: Unit
        #     if enemy.detect_range > 0 and enemy.detect_range > target.distance_to(enemy):
        #         break

        if self.pather.map.vision_status(unit.position) == VisionStatus.Detected:
            target = self.pather.find_weak_influence_air(unit.position, 12)
        elif enemies:
            target = self.pather.find_weak_influence_air(target, 12)

        return Action(target, False)
