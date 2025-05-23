from sc2.ids.ability_id import AbilityId
from sharpy.combat import MicroStep, Action
from sc2.unit import Unit
from sc2.units import Units


class MicroOverseers(MicroStep):
    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if isinstance(current_command.target, Unit):
            target_pos = current_command.target.position
        else:
            target_pos = current_command.target

        target = self.pather.find_path(self.group.center, target_pos, 20)
        enemies = self.cache.enemy_in_range(target, 40)

        if enemies:
            if self.cd_manager.is_ready(unit.tag, AbilityId.SPAWNCHANGELING_SPAWNCHANGELING):
                return Action(None, False, AbilityId.SPAWNCHANGELING_SPAWNCHANGELING)

        for enemy in enemies:  # type: Unit
            if enemy.detect_range > 0 and enemy.detect_range > target.distance_to(enemy):
                target = self.pather.find_weak_influence_air(target, 100)
                break

        return Action(target, False)
