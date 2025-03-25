from math import ceil
from typing import TYPE_CHECKING
from sharpy.plans.acts import ActBase
from sharpy.managers.core.roles import UnitTask
from sharpy.general.zone import Zone
from sc2.constants import UnitTypeId
from sc2.unit import Unit

if TYPE_CHECKING:
    from sharpy.managers.core import UnitRoleManager


class Repair(ActBase):
    def __init__(self):
        super().__init__()

    async def execute(self) -> bool:
        roles: "UnitRoleManager" = self.roles
        current_repairers = []
        for zone in self.zone_manager.our_zones:
            pre_repairer = 0
            balance = zone.our_power.power - zone.assaulting_enemy_power.power
            if balance < -50:
                if balance < +100:
                    pre_repairer = 6
                else:
                    pre_repairer = 3

            repairing_zone_count = 0

            for worker in zone.our_workers:  # type: Unit
                if not worker.orders:
                    continue
                if worker.is_repairing:
                    current_repairers.append(worker.tag)
                    roles.set_task(UnitTask.Building, worker)
                    repairing_zone_count += 10

            for unit in zone.our_units:
                if self.should_repair(unit):
                    desired_count = self.solve_scv_count(zone, unit)

                    if repairing_zone_count < desired_count:
                        for worker in zone.our_workers:  # type: Unit
                            if not worker.is_repairing and worker.tag not in current_repairers:
                                worker.repair(unit)
                                current_repairers.append(worker.tag)
                                roles.set_task(UnitTask.Building, worker)
                                repairing_zone_count += 10
                                if repairing_zone_count >= desired_count:
                                    break

            if repairing_zone_count < pre_repairer:
                to_repair = zone.our_units.filter(lambda u: u.is_ready and (u.is_structure or u.is_mechanical))
                enemies = zone.known_enemy_units
                if to_repair and enemies:
                    for worker in zone.our_workers:  # type: Unit
                        if not worker.is_repairing and worker.tag not in current_repairers:
                            closest = to_repair.closest_to(enemies.center)
                            worker.repair(closest)
                            current_repairers.append(worker.tag)
                            roles.set_task(UnitTask.Building, worker)
                            repairing_zone_count += 10
                            if repairing_zone_count >= pre_repairer:
                                break

        return True

    def should_repair(self, unit: Unit) -> bool:
        if not unit.is_ready:
            return False
        if unit.health_percentage < 0.95:
            if unit.type_id == UnitTypeId.BUNKER:
                return True
            elif (
                unit.type_id == UnitTypeId.COMMANDCENTER
                or unit.type_id == UnitTypeId.ORBITALCOMMAND
                or unit.type_id == UnitTypeId.PLANETARYFORTRESS
                or unit.type_id == UnitTypeId.BATTLECRUISER
                or unit.type_id == UnitTypeId.BANSHEE
                or unit.type_id == UnitTypeId.VIKINGFIGHTER
            ):
                return True
        if unit.health_percentage < 0.85 and unit.is_structure:
            return True
        if unit.health_percentage < 0.75 and unit.is_mechanical:
            return True
        return False

    def solve_scv_count(self, zone: Zone, unit: Unit) -> int:
        power_max = max(100, zone.known_enemy_power.power / 70)
        if unit.type_id == UnitTypeId.BUNKER:
            hp_min = 100
        elif (
            unit.type_id == UnitTypeId.COMMANDCENTER
            or unit.type_id == UnitTypeId.ORBITALCOMMAND
            or unit.type_id == UnitTypeId.PLANETARYFORTRESS
            or unit.type_id == UnitTypeId.BATTLECRUISER
            or unit.type_id == UnitTypeId.BANSHEE
            or unit.type_id == UnitTypeId.VIKINGFIGHTER
        ):
            hp_min = 160
        elif unit.is_structure:
            hp_min = 50
        else:
            hp_min = 60
        return ceil(min(power_max, hp_min))
