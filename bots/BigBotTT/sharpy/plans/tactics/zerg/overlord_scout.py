from typing import List, Optional

from sc2.position import Point2
from sc2.ids.unit_typeid import UnitTypeId
from sharpy.plans.tactics.scouting import ScoutBaseAction, Scout
from sharpy.plans.tactics.scouting import ScoutLocation


class OverlordScout(Scout):
    def __init__(self, *args: ScoutLocation.scout_enemy3):
        super().__init__(UnitTypeId.OVERLORD, 1, *args)
