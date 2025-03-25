from typing import Optional

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.units import Units
from sharpy.general.extended_power import ExtendedPower
from sharpy.general.zone import Zone
from sharpy.combat import MoveType
from sharpy.managers.core.roles import UnitTask
from sharpy.plans.tactics import PlanZoneAttack
from sc2.position import Point2
from sharpy.plans.tactics.zone_attack import AttackStatus


class DodgeRampAttack(PlanZoneAttack):
    async def execute(self) -> bool:
        enemy_main: Zone = self.zone_manager.expansion_zones[-1]
        enemy_natural: Zone = self.zone_manager.expansion_zones[-2]

        if enemy_main.is_enemys and not enemy_natural.is_enemys:
            # enemy controls their main, but does not control their natural
            for effect in self.ai.state.effects:
                if effect.id != "FORCEFIELD":
                    continue
                pos: Point2 = enemy_main.ramp.bottom_center
                for epos in effect.positions:
                    if pos.distance_to_point2(epos) < 5:
                        return await self.small_retreat(enemy_natural)

        return await super().execute()

    def _should_attack(self, power: ExtendedPower) -> bool:
        result = super()._should_attack(power)
        if not result and len(self.ai.workers) < 2 and power.ground_power > 1:
            # Last desperate attack.
            return True
        return result

    async def small_retreat(self, natural: Zone):
        attacking_units = self.roles.attacking_units

        for unit in attacking_units:
            self.combat.add_unit(unit)

        path = natural.paths.get(0, None)
        target = natural.center_location

        if path and path.distance > 50:
            target = path.get_index(8)

        self.combat.execute(target, MoveType.DefensiveRetreat)
        return False

    def handle_attack(self, target):
        already_attacking: Units = self.roles.units(UnitTask.Attacking)
        if not already_attacking.exists:
            self.print("No attacking units, starting retreat")
            # All attacking units have been destroyed.
            self._start_retreat(AttackStatus.Retreat)
            return True

        center = already_attacking.center
        front_runner = already_attacking.closest_to(target)

        for unit in already_attacking:
            # Only units in group are included to current combat force
            self.combat.add_unit(unit)

        self.roles.refresh_tasks(already_attacking)

        for unit in self.roles.free_units:
            if self.unit_values.should_attack(unit):
                if not self.roles.is_in_role(UnitTask.Attacking, unit) and (
                    unit.distance_to(center) > 20 or unit.distance_to(front_runner) > 20
                ):
                    self.roles.set_task(UnitTask.Moving, unit)
                    # Unit should start moving to target position.
                    self.combat.add_unit(unit)
                else:
                    self.roles.set_task(UnitTask.Attacking, unit)
                    already_attacking.append(unit)
                    # Unit should start moving to target position.
                    self.combat.add_unit(unit)

        # Execute
        self.combat.execute(target, MoveType.Assault)

        retreat = self._should_retreat(front_runner.position, already_attacking)

        if retreat != AttackStatus.NotActive:
            self._start_retreat(retreat)

    def _get_target(self) -> Optional[Point2]:
        our_main = self.zone_manager.expansion_zones[0].center_location
        proxy_buildings = self.ai.enemy_structures.closer_than(70, our_main)

        if proxy_buildings.exists:
            return proxy_buildings.closest_to(our_main).position

        # Select expansion to attack.
        # Enemy main zone should the last element in expansion_zones.
        enemy_zones = list(filter(lambda z: z.is_enemys, self.zone_manager.expansion_zones))

        best_zone = None
        best_score = 100000
        start_position = self.gather_point_solver.gather_point
        if self.roles.attacking_units:
            start_position = self.roles.attacking_units.center

        for zone in enemy_zones:  # type: Zone
            not_like_points = zone.center_location.distance_to(start_position)
            not_like_points += zone.enemy_static_power.power * 5
            if zone.zone_index == len(self.zone_manager.expansion_zones) - 1:
                # Enemy main base.
                # Add natural defense to not liked points
                not_like_points += self.zone_manager.expansion_zones[-2].enemy_static_power.power * 5

                if self.game_analyzer.army_at_least_clear_advantage and self.ai.enemy_race == Race.Terran:
                    # Just go kill enemy production in their main
                    not_like_points -= 30

            if not_like_points < best_score:
                best_zone = zone
                best_score = not_like_points

        if best_zone is not None:
            return best_zone.center_location

        if self.ai.enemy_structures.exists:
            return self.ai.enemy_structures.closest_to(our_main).position

        return None
