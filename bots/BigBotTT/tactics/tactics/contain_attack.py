from typing import Optional

from sc2.position import Point2
from sc2.units import Units
from sharpy.general.zone import Zone
from sharpy.interfaces import IZoneManager
from sharpy.interfaces.combat_manager import MoveType
from sharpy.managers.core.roles import UnitTask
from sharpy.plans.acts import ActBase


class ContainAttack(ActBase):
    zone_manager: IZoneManager
    pather: "PathingManager"

    def __init__(self) -> None:
        super().__init__()

    async def execute(self) -> bool:
        target = self._get_target()
        if target is None:
            # Nothing to attack
            return True

        # Attack
        self.handle_attack(target)

    def handle_attack(self, target: Point2):
        already_attacking: Units = self.roles.units(UnitTask.Attacking)

        if already_attacking:
            center = already_attacking.center
            front_runner = already_attacking.closest_to(target)
        else:
            center = None
            front_runner = None

        for unit in already_attacking:
            # Only units in group are included to current combat force
            self.combat.add_unit(unit)

        self.roles.refresh_tasks(already_attacking)
        had_units_count = len(already_attacking)

        for unit in self.roles.free_units:
            if self.unit_values.should_attack(unit):
                if (
                    center
                    and front_runner
                    and not self.roles.is_in_role(UnitTask.Attacking, unit)
                    and (unit.distance_to(center) > 20 or unit.distance_to(front_runner) > 20)
                ):
                    self.roles.set_task(UnitTask.Moving, unit)
                    # Unit should start moving to target position.
                    self.combat.add_unit(unit)
                else:
                    self.roles.set_task(UnitTask.Attacking, unit)
                    already_attacking.append(unit)
                    # Unit should start moving to target position.
                    self.combat.add_unit(unit)

        if had_units_count == 0 and len(already_attacking) > 0:
            self.print(f"Attacking to {target}")

        # Execute
        self.combat.execute(target, MoveType.Assault)

    def _get_target(self) -> Optional[Point2]:
        our_main = self.zone_manager.expansion_zones[0].center_location
        proxy_buildings = self.ai.enemy_structures.closer_than(70, our_main)

        if proxy_buildings.exists:
            return proxy_buildings.closest_to(our_main).position

        # Select expansion to attack.
        best_zone = None
        for i in range(0, len(self.zone_manager.expansion_zones) - 2):
            zone = self.zone_manager.expansion_zones[i]
            if zone.is_enemys:
                best_zone = zone
                break

        natural = self.zone_manager.enemy_expansion_zones[1]
        enemy_main = self.zone_manager.enemy_expansion_zones[0]

        if not best_zone and natural.is_enemys:
            if natural.ramp is not None:
                return natural.ramp.bottom_center.towards(natural.center_location, -10)
            else:
                target = Point2(natural.paths[0].get_index(22))
        elif self.zone_manager.enemy_expansion_zones[0].is_enemys:
            best_zone = natural  # Don't attack main
            # try to find a decent position to hold
            if natural.ramp is not None:
                return natural.ramp.top_center
            else:
                target = Point2(natural.paths[0].get_index(6))
                if enemy_main.ramp is not None:
                    target = target.towards(enemy_main.ramp.bottom_center, -3)
                return target

        if best_zone is not None:
            return best_zone.center_location

        if self.ai.enemy_structures.exists:
            return self.ai.enemy_structures.closest_to(our_main).position

        return None
