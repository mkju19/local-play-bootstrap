from typing import Optional

from tactics.micro.harvester_micro_methods import ignored_types
from sharpy import sc2math
from sharpy.combat import MicroStep
from sharpy.combat import Action
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units


class MicroProbes(MicroStep):
    choke_minerals: Units
    choke_mf: Optional[Unit]
    choke_wp: Optional[Point2]

    def __init__(self):

        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.choke_minerals = Units([], self.ai)
        close_mf = self.ai.mineral_field.closer_than(10, self.ai.start_location)
        self.choke_minerals: Units

        for mf in close_mf:  # type: Unit
            chokeable = 0
            for choke_mf in close_mf:  # type: Unit
                if abs(choke_mf.position.x - mf.position.x) <= 2 and abs(choke_mf.position.y - mf.position.y) <= 1:
                    chokeable += 1

            if chokeable > 2:
                self.choke_minerals.append(mf)

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        self.choke_mf = None
        self.choke_wp = None

        if self.engaged_power.melee_percentage >= 1:
            # Detect mineral chokes
            if self.closest_group and self.choke_minerals:
                choke = self.closest_group.center.closest(self.choke_minerals)
                choke_wp = choke.position.towards(self.ai.start_location, 0.9)
                if choke and choke_wp.distance_to(self.closest_group.center) < 1.3:
                    # The enemy is trying to choke drone drill
                    self.choke_mf = choke
                    self.choke_wp = choke_wp

        # for choke in self.choke_minerals:  # type: Unit
        #     choke_wp = choke.position3d.towards(self.ai.start_location, 0.9)
        #     self.debug_text_on_unit(choke, "CHOKE!")
        #     # self.client.debug_line_out(choke, choke_wp)
        #     self.client.debug_sphere_out(choke_wp, 1.3)

        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        self.debug_text_on_unit(unit, str(round(unit.weapon_cooldown)))

        if self.engaged_power.power > 1 and self.closest_group and self.engaged_power.melee_percentage > 0.9:
            backstep: Point2 = unit.position.towards(self.closest_group.center, -3)

            if (unit.health + unit.shield <= 5 and not self.ready_to_shoot(unit)) or (
                unit.shield_health_percentage < 0.5 and unit.weapon_cooldown > 9
            ):
                backstep = self.pather.find_weak_influence_ground(backstep, 4)
                if self.cache.own_in_range(unit.position, 1) or self.cache.enemy_in_range(unit.position, 1):
                    # Mineral walk
                    angle = sc2math.line_angle(unit.position, backstep)
                    best_angle = sc2math.pi / 6
                    best_mf = None

                    for mf in self.ai.mineral_field:  # type: Unit
                        new_angle = sc2math.line_angle(unit.position, mf.position)
                        angle_distance = sc2math.angle_distance(angle, new_angle)
                        if angle_distance < best_angle:
                            best_mf = mf
                            best_angle = angle_distance

                    if best_mf:
                        # Use backstep with gather command to pass through own units
                        return Action(best_mf, False, ability=AbilityId.HARVEST_GATHER)
                return Action(backstep, False)

            # if unit.weapon_cooldown < cd and self.choke_mf:
            if self.choke_mf:
                # Offensive step forward, designed to fight against drills
                closest = self.closest_units.get(unit.tag)
                if closest:  # and closest.distance_to(unit) > self.unit_values.real_range(unit, closest):

                    if self.choke_mf:
                        angle = sc2math.line_angle(self.choke_mf.position, self.ai.start_location)
                        angle_unit = sc2math.line_angle(self.choke_mf.position, unit.position)
                        angle_distance = sc2math.angle_distance(angle, angle_unit)
                        if angle_distance < sc2math.pi / 4:

                            if unit.weapon_cooldown < 3 and unit.distance_to(self.choke_mf) < 2:
                                current = Action(closest.position, True)
                                return self.probe_focus_fire(unit, current)
                            # Use forward step with gather command to pass through own units
                            return Action(self.choke_mf, False, ability=AbilityId.HARVEST_GATHER)
                        else:
                            return Action(self.choke_mf.position.towards(self.ai.start_location, 4), False)

        # if self.ready_to_shoot(unit):
        #     if unit.is_attacking and unit.order_target is int:
        #         # Continue attacking the current target
        #         target = self.cache.by_tag(unit.order_target)
        #         if target and unit.distance_to(target) < self.unit_values.real_range(unit, target):
        #             return Action(target, True)
        #
        # closest = self.closest_units.get(unit.tag)
        # if closest:
        #     d = closest.distance_to(unit)
        #     if d > self.unit_values.real_range(unit, closest) or (unit.weapon_cooldown > 5 and d > 0.25):
        #         base_angle = sc2math.line_angle(unit.position, closest.position)
        #         angle_unit = None
        #         best_angle = sc2math.pi / 4
        #
        #         for mf in self.ai.mineral_field.closer_than(4, unit):
        #             if mf.distance_to(unit) > d:
        #                 angle = sc2math.line_angle(unit.position, mf.position)
        #                 angle_distance = sc2math.angle_distance(base_angle, angle)
        #                 if angle_distance < best_angle:
        #                     angle_unit = mf
        #                     best_angle = angle_distance
        #
        #         if angle_unit:
        #             return Action(angle_unit, False, ability=AbilityId.HARVEST_GATHER)

        if self.ready_to_shoot(unit):
            if self.closest_group:
                current = Action(self.closest_group.center, True)
            else:
                current = Action(current_command.target, True)
            return self.melee_focus_fire(unit, current)
            # return self.probe_focus_fire(unit, current)

        return current_command

    def probe_focus_fire(self, unit: Unit, current_command: Action) -> Action:
        ground_range = self.unit_values.ground_range(unit)
        lookup = ground_range + 3
        enemies = self.cache.enemy_in_range(unit.position, lookup)

        last_target = self.last_targeted(unit)

        if not enemies:
            # No enemies to shoot at
            return current_command

        def melee_value(u: Unit):
            val = max(0, 40 - enemy.health - enemy.shield) / 40
            att_range = self.unit_values.real_range(unit, u)
            distance = unit.position.distance_to(u.position)
            val += 1 - distance / lookup
            if unit.distance_to(u) < att_range:
                val += 3
            if self.knowledge.enemy_race == Race.Terran and unit.is_structure and unit.build_progress < 1:
                # if building isn't finished, focus on the possible scv instead
                val -= 2
            return val

        close_enemies = self.cache.enemy_in_range(unit.position, lookup)

        best_target: Optional[Unit] = None
        best_score: float = 0

        for enemy in close_enemies:  # type: Unit
            if enemy.type_id in ignored_types:
                continue

            if enemy.is_flying:
                continue

            score = melee_value(enemy)
            if enemy.tag == last_target:
                score += 1

            if self.focus_fired.get(enemy.tag, 0) > enemy.health + 1:
                score *= 0.1

            if score > best_score:
                best_target = enemy
                best_score = score

        if best_target:
            self.focus_fired[best_target.tag] = self.focus_fired.get(best_target.tag, 0)
            return Action(best_target, True)

        return current_command
