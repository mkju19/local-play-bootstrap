from typing import Set

from sharpy.plans.acts import ActBase
from sharpy.managers.core import UnitRoleManager
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from sharpy.managers.core.roles import UnitTask
from sharpy.knowledges import Knowledge


class PlanHallucination(ActBase):
    """Keeps track of our own hallucinated units."""

    def __init__(self):
        super().__init__()
        self.roles: UnitRoleManager = None
        self.resolved_units_tags: Set[int] = set()

        # Types that we currently use for hallucinations
        self.types: Set[UnitTypeId] = {
            UnitTypeId.COLOSSUS,
            UnitTypeId.PHOENIX,
            UnitTypeId.VOIDRAY,
            UnitTypeId.IMMORTAL,
            UnitTypeId.ARCHON,
            UnitTypeId.STALKER,
            UnitTypeId.ZEALOT,
        }

    async def start(self, knowledge: Knowledge):
        await super().start(knowledge)
        self.roles = knowledge.roles

    async def execute(self) -> bool:
        filtered_units = self.cache.own(self.types).tags_not_in(self.resolved_units_tags)

        for unit in filtered_units:  # type: Unit
            if unit.is_hallucination:
                await self.hallucination_detected(unit)

            self.resolved_units_tags.add(unit.tag)

        units = self.roles.units(UnitTask.Hallucination)
        if units.exists:
            self.roles.refresh_tasks(units)
            if self.ai.enemy_units.exists:
                target = self.ai.enemy_units.center
            else:
                target = self.zone_manager.enemy_main_zone.center_location

            for unit in self.roles.units(UnitTask.Hallucination):
                unit.attack(target)

        return True

    async def hallucination_detected(self, unit):
        self.roles.set_task(UnitTask.Hallucination, unit)
        self.print(f"{unit.type_id.name} {unit.tag} detected as hallucination")
