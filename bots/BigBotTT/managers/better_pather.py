from sc2pathlib import MapType
from sharpy.managers.core import PathingManager


class BetterPather(PathingManager):
    async def update_influence(self):
        await super().update_influence()

        if (
            self.zone_manager.expansion_zones[0].is_ours
            and not self.zone_manager.expansion_zones[1].is_ours
            and not self.zone_manager.expansion_zones[2].is_ours
        ):
            if self.zone_manager.expansion_zones[0].assaulting_enemy_power.power > 2:
                self.map.add_influence_to_vision(MapType.Ground, 2000, 2000)
                # self.map.add_influence_without_zones([1], 2000)
