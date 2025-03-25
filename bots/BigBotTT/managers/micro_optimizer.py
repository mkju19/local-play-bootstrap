from typing import Tuple, List

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit
from sharpy.managers.core import ManagerBase
from sharpy.managers.core.roles import UnitTask
from sharpy.managers.extensions import BuildDetector


class MicroOptimizer(ManagerBase):
    def __init__(self) -> None:
        self.started = False
        self.ended = False
        self.old_step_size = 0
        self.stats: List[Tuple[float, int]] = []
        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.build_detector = knowledge.get_required_manager(BuildDetector)

    async def update(self):
        if self.build_detector.worker_rush_detected and self.ai.supply_workers > 0:
            self.started = True
            self.old_step_size = self.ai.client.game_step

        if not self.started:
            return

        self.ai.client.game_step = 1

        if self.ai.time > 180:
            self.started = False
            self.ended = True
            self.ai.client.game_step = self.old_step_size

        # count = 0
        # ready_to_shoot = 0
        # cooldown = 0
        # for probe in self.roles.get_types_from({UnitTypeId.PROBE}, UnitTask.Defending):  # type: Unit
        #     count += 1
        #     cooldown += probe.weapon_cooldown
        #     if probe.weapon_cooldown <= 0:
        #         ready_to_shoot += 1
        #
        # if count > 0:
        #     avg = cooldown / count
        #     self.stats.append((avg, ready_to_shoot))
        #
        # if len(self.cache.own(UnitTypeId.PROBE)) == 0 or len(self.cache.enemy(UnitTypeId.DRONE)) == 0:
        #     self.started = False
        #     avg_sum = 0
        #     frames = 0
        #
        #     for avg in self.stats:
        #         avg_sum += avg[0]
        #         frames += avg[1]
        #     avg_sum = avg_sum / len(self.stats)
        #     frames = frames / len(self.stats)
        #     self.print(f"Average: {avg_sum} Not attacking average: {frames} Frames: {len(self.stats)}")

    async def post_update(self):
        pass
