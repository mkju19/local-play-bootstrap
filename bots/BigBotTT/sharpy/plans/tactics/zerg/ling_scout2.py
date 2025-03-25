from sc2.ids.unit_typeid import UnitTypeId
from sharpy.plans.tactics import Scout
from sharpy.plans.tactics.scouting import ScoutLocation


class LingScout2(Scout):
    def __init__(self, unit_count: int = 1, *args: ScoutLocation.scout_enemy3):
        super().__init__(UnitTypeId.ZERGLING, unit_count, *args)
