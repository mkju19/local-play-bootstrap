import math

from sc2.position import Point2
from sc2.unit import Unit

from sc2 import UnitTypeId, AbilityId
from sharpy.combat import MicroStep
from sharpy.combat.group_combat_manager import GroupCombatManager
from sharpy.general.extended_power import ExtendedPower
from sharpy.interfaces import IGameAnalyzer
from sharpy.interfaces.combat_manager import MoveType
from sharpy.managers.core.version_manager import GameVersion
from sharpy.managers.extensions.game_states.advantage import at_least_clear_advantage, Advantage

beams = {UnitTypeId.VOIDRAY, UnitTypeId.SENTRY}


class CombatMethods:
    @staticmethod
    def ready_to_shoot(step: MicroStep, unit: Unit) -> bool:
        if step.knowledge.version_manager.base_version >= GameVersion.V_5_0_0 and unit.type_id in beams:
            return True

        if unit.type_id == UnitTypeId.ZEALOT:
            if unit.weapon_cooldown > 17:
                return True

        if unit.type_id == UnitTypeId.CYCLONE:
            if step.cd_manager.is_ready(unit.tag, AbilityId.CANCEL_LOCKON):
                return False

        if unit.type_id == UnitTypeId.DISRUPTOR:
            return step.cd_manager.is_ready(unit.tag, AbilityId.EFFECT_PURIFICATIONNOVA)

        if unit.type_id == UnitTypeId.ORACLE:
            tick = step.ai.state.game_loop % 16  # 13,664
            return tick < 7 + step.client.game_step

        if unit.type_id == UnitTypeId.CARRIER:
            if not unit.passengers:
                return False
            tick = step.ai.state.game_loop % 48  # 47.936
            return tick < 20

        # 4.032630300115908 step time for turning 180 degrees
        closest = step.closest_units.get(unit.tag)

        if closest:
            distance = unit.distance_to(closest)
            range = step.unit_values.real_range(unit, closest)

            angle_to = math.atan2(*reversed(closest.position - unit.position))
            if angle_to < 0:
                angle_to += math.pi * 2

            angle_diff = math.fabs(angle_to - unit.facing)
            turnrate = math.pi / 180 * 999.8437  # most common turn rate

            turntime = angle_diff / turnrate
            if step.ai.realtime:
                steptime = 4 / 22.4
            else:
                steptime = step.client.game_step / 22.4

            if unit.real_speed <= 0:
                movetime = 0
            else:
                movetime = max(0, (distance - range) / (unit.real_speed * 1.4))

            cooldown = unit.weapon_cooldown / 22.4

            return cooldown < min(steptime + 1.5, turntime + steptime + movetime)

        if step.ai.realtime:
            delay_to_shoot = 4.5  # 3 + 1.5 to be on the safe side of things
        else:
            delay_to_shoot = step.client.game_step + 1.5

        return unit.weapon_cooldown <= delay_to_shoot

    @staticmethod
    def handle_groups(combat: "GroupCombatManager", target: Point2, move_type=MoveType.Assault):
        total_power = ExtendedPower(combat.unit_values)

        for group in combat.own_groups:
            total_power.add_power(group.power)

            regroup_center = Point2((0, 0))
            added = 0
            for unit in group.units:
                if unit.type_id == UnitTypeId.IMMORTAL or unit.type_id == UnitTypeId.COLOSSUS:
                    regroup_center += unit.position
                    added += 1
            if added > 0:
                group.center = regroup_center / added

        for group in combat.own_groups:
            if not combat.rules.regroup or combat.regroup_threshold <= 0:
                # Skip all regroup logic
                if move_type == MoveType.PanicRetreat:
                    combat.move_to(group, target, move_type)
                else:
                    combat.attack_to(group, target, move_type)
                continue

            center = group.center

            closest_enemies = group.closest_target_group(combat.enemy_groups)

            if move_type == MoveType.Assault:
                # Group towards attack target
                own_closest_group = combat.closest_group(target, combat.own_groups, center, 999)
            else:
                # Group up with closest group
                own_closest_group = combat.closest_group(center, combat.own_groups)

            if len(combat.own_groups) > 1 and group.power.ground_power == 0 and group.power.air_power == 0:
                # Support group, i.e. warp prism or observer
                # Group up with closest group

                if own_closest_group:
                    combat.move_to(group, own_closest_group.center, MoveType.ReGroup)
                    continue

            if closest_enemies is None:
                if move_type == MoveType.PanicRetreat:
                    combat.move_to(group, target, move_type)
                else:
                    combat.attack_to(group, target, move_type)
            else:
                power = group.power
                enemy_power = ExtendedPower(combat.unit_values)
                enemy_power.add_units(closest_enemies.units)

                is_in_combat = group.is_in_combat(closest_enemies)

                if move_type == MoveType.DefensiveRetreat or move_type == MoveType.PanicRetreat:
                    combat.move_to(group, target, move_type)
                    break

                if power.power > combat.regroup_threshold * total_power.power:
                    # Most of the army is here
                    if is_in_combat or not group.is_too_spread_out():
                        combat.attack_to(group, target, move_type)
                    else:
                        combat.regroup(group, group.center)

                elif move_type == MoveType.Push:
                    # Don't worry about closest enemies if we are pushing
                    combat.attack_to(group, target, move_type)

                elif is_in_combat:
                    if not power.is_enough_for(enemy_power, 0.75):
                        # Regroup if possible

                        if own_closest_group:
                            combat.move_to(group, own_closest_group.center, MoveType.ReGroup)
                        else:
                            # fight to bitter end
                            combat.attack_to(group, closest_enemies.center, move_type)
                    else:
                        combat.attack_to(group, closest_enemies.center, move_type)
                else:
                    analyzer: IGameAnalyzer = combat.ai.game_analyzer

                    if analyzer.our_army_predict == Advantage.OverwhelmingAdvantage:
                        # We have enough units here to crush everything the enemy has even with an half assed attack
                        combat.attack_to(group, closest_enemies.center, move_type)
                    else:
                        # regroup if the current group is simply too small
                        if own_closest_group and power.power < 0.2 * total_power.power:
                            combat.regroup(group, own_closest_group.center)
                        # Regroup if possible
                        elif own_closest_group:
                            combat.regroup(group, own_closest_group.center)
                        elif group.is_too_spread_out():
                            combat.regroup(group, group.center)
                        else:
                            # fight to bitter end
                            combat.attack_to(group, closest_enemies.center, move_type)
