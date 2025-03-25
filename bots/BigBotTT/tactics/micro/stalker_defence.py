from typing import List, Any, Tuple

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from sc2pathlib import PathFinder
from sharpy.combat.protoss import MicroStalkers
from sharpy.general.extended_power import ExtendedPower
from sharpy.combat import CombatUnits, MoveType, Action


class ExtendedMicroStalkers(MicroStalkers):
    def init_group(
        self,
        rules: "MicroRules",
        group: CombatUnits,
        units: Units,
        enemy_groups: List[CombatUnits],
        move_type: MoveType,
        original_target: Point2,
    ):
        super().init_group(rules, group, units, enemy_groups, move_type, original_target)
        self.defender_tag = None
        self.chaser_tag = None

        if (
            move_type == MoveType.SearchAndDestroy
            and len(self.enemies_near_by) < 4
            and 1 <= self.enemies_near_by.of_type(UnitTypeId.REAPER).amount <= 2
            and self.ai.workers.exists
        ):
            sorted_units = units.sorted(lambda u: u.tag)

            if len(sorted_units) > 0:
                self.defender_tag = sorted_units[0].tag
            if len(sorted_units) > 1:
                self.chaser_tag = sorted_units[1].tag

            self.reaper_defence = True
            data = self.pather.map._map.reaper_pathing
            self.reverse_reaper = PathFinder(data)

            power = ExtendedPower(self.unit_values)

            for unit_type in self.cache.own_unit_cache:  # type: UnitTypeId
                units: Units = self.cache.own_unit_cache.get(unit_type, Units([], self.ai))
                if len(units) == 0:
                    continue

                example_unit: Unit = units[0]
                power.clear()
                power.add_unit(unit_type, 100)

                if self.unit_values.can_shoot_ground(example_unit):
                    positions = [unit.position for unit in units]
                    s_range = self.unit_values.ground_range(example_unit)
                    if example_unit.type_id == UnitTypeId.CYCLONE:
                        s_range = 7

                    if s_range < 2:
                        self.reverse_reaper.add_influence_walk(positions, power.ground_power, 7)
                    elif s_range < 5:
                        self.reverse_reaper.add_influence_walk(positions, power.ground_power, 7)
                    else:
                        self.reverse_reaper.add_influence(positions, power.ground_power, s_range + 3)
        else:
            self.reaper_defence = False

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:

        if self.reaper_defence and (not self.ready_to_shoot(unit) or not self.enemies_near_by.closer_than(6, unit)):

            # Do reverse reaper mapping defense
            if self.defender_tag == unit.tag:
                worker = self.ai.workers.closest_to(unit)
                reaper = self.enemies_near_by(UnitTypeId.REAPER).closest_to(worker)
                worker = self.ai.workers.closest_to(reaper)
                # target = Point2(self.reverse_reaper.find_low_inside_walk(reaper.position, worker.position, 3)[0])
                # self.client.debug_line_out(unit.position3d, Point3((target.x, target.y, unit.position3d.z)))
                # return Action(target, False)
                path = self.reverse_reaper.find_path_influence(reaper.position, worker.position)
                return self.draw_path_defense(unit, path, current_command)
            if self.chaser_tag == unit.tag:
                reaper = self.enemies_near_by(UnitTypeId.REAPER).closest_to(unit)
                escape_location = self.zone_manager.enemy_start_location
                path = self.reverse_reaper.find_path_influence(reaper.position, escape_location)
                return self.draw_path_defense(unit, path, current_command)
        return super().unit_solve_combat(unit, current_command)

    def draw_path_defense(self, unit: Unit, path: Tuple[Any], current_command: Action) -> Action:
        target = None
        if len(path[0]) > 5:
            target = Point2(path[0][5])
        elif path[1] > 0:
            target = Point2(path[0][-1])
        if target:
            if self.debug:
                self.client.debug_line_out(unit.position3d, Point3((target.x, target.y, unit.position3d.z)))
            return Action(target, False)
        return super().unit_solve_combat(unit, current_command)
