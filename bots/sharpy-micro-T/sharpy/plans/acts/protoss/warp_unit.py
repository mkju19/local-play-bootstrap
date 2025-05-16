from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sharpy.interfaces import IGatherPointSolver, IZoneManager
from sharpy.managers.core import PathingManager

from sharpy.managers.core.roles import UnitTask
from sc2.units import Units
from sharpy.plans.acts.act_base import ActBase


class WarpUnit(ActBase):
    """Use Warp Gates (Protoss) to build units."""

    gather_point_solver: IGatherPointSolver
    zone_manager: IZoneManager

    def __init__(self, unit_type: UnitTypeId, to_count: int = 9999, priority: bool = False):
        assert unit_type is not None and isinstance(unit_type, UnitTypeId)
        assert to_count is not None and isinstance(to_count, int)
        assert isinstance(priority, bool)

        self.unit_type = unit_type
        self.to_count = to_count
        self.priority = priority

        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.gather_point_solver = knowledge.get_required_manager(IGatherPointSolver)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)
        self.pather = knowledge.get_manager(PathingManager)

    @property
    def is_done(self) -> bool:
        unit_count = self.cache.own(self.unit_type).amount
        return unit_count >= self.to_count

    async def ready_to_warp(self, warpgate: Unit):
        # all the units have the same cooldown anyway so let's just look at ZEALOT
        return self.cd_manager.is_ready(warpgate.tag, AbilityId.WARPGATETRAIN_ZEALOT)

    async def execute(self) -> bool:
        if self.is_done:
            return True

        warpgates = self.cache.own(UnitTypeId.WARPGATE)
        attackers: Units = self.roles.units(UnitTask.Attacking)

        unit_type = self.unit_type
        if unit_type == UnitTypeId.ARCHON:
            unit_type = UnitTypeId.HIGHTEMPLAR

        if warpgates.ready.exists and self.knowledge.can_afford(unit_type):
            if not self.cache.own(UnitTypeId.PYLON).ready.exists:
                return True  # Can't proceed

            target_point = self.gather_point_solver.gather_point
            if len(attackers) > 0:
                target_point = self.zone_manager.enemy_main_zone.center_location

            for zone in self.zone_manager.expansion_zones:
                if zone.is_ours and zone.known_enemy_power.power > 0:
                    target_point = zone.center_location
                    break

            nexuses: Units = self.cache.own(UnitTypeId.NEXUS)
            if nexuses:
                # Reset position to nexus to reduce the possibility of warping stuck units in.
                target_point = nexuses.closest_to(target_point).position

            near_position = self.cache.own(UnitTypeId.PYLON).ready.closest_to(target_point).position

            phasing = self.cache.own(UnitTypeId.WARPPRISMPHASING)
            warpprisms = self.cache.own(UnitTypeId.WARPPRISM)
            if phasing:
                near_position = phasing.closest_to(target_point).position
            elif warpprisms and len(attackers) > 1:
                if warpprisms[0].tag in attackers.tags:
                    # Waiting for warp prism
                    return False

            for warpgate in warpgates.ready:
                if await self.ready_to_warp(warpgate):
                    pos = near_position.to2.random_on_distance(6)
                    placement = await self.ai.find_placement(AbilityId.WARPGATETRAIN_STALKER, pos, placement_step=1)
                    if placement is None:
                        # return ActionResult.CantFindPlacementLocation
                        self.knowledge.print("can't find place to warp in")
                        return False
                    if not self.pather or self.pather.map.is_connected(placement):
                        warpgate.warp_in(unit_type, placement)

        elif self.priority:
            unit = self.ai._game_data.units[unit_type.value]
            cost = self.ai._game_data.calculate_ability_cost(unit.creation_ability)
            self.knowledge.reserve(cost.minerals, cost.vespene)
        return False
