import enum

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sharpy.managers.extensions import BuildDetector, ChatManager
from sharpy.managers.extensions.build_detector import EnemyRushBuild


class ExtendedEnemyRushBuild(enum.IntEnum):
    Macro = 0
    Pool12 = 1
    CannonRush = 2
    ProxyRax = 3
    OneBaseRax = 4
    ProxyZealots = 5
    Zealots = 6
    OneHatcheryAllIn = 7
    PoolFirst = 8
    RoachRush = 9
    Marauders = 10
    HatchPool15_14 = 11
    ProxyRobo = 12
    RoboRush = 13
    AdeptRush = 14
    WorkerRush = 15
    LateWorkerRush = 1000
    # Terran
    # Zerg
    ProxyHatchery = 1001
    # Protoss


class EnemyMacroBuild(enum.IntEnum):
    StandardMacro = 0
    BattleCruisers = 1
    Banshees = 2
    Tempests = 3
    Carriers = 4
    DarkTemplars = 5
    Lurkers = 6
    Mutalisks = 7
    Mmm = 8


class ExtendedBuildDetector(BuildDetector):
    chat_manager: ChatManager

    async def start(self, knowledge: "Knowledge"):
        self.chat_manager = knowledge.get_required_manager(ChatManager)
        return await super().start(knowledge)

    async def update(self):
        await super().update()
        if self.ai.time > 200:
            await self.chat_manager.chat_taunt_once(
                "EnemyRush", lambda: "Tag:rush_" + self.rush_build.name, team_only=True
            )
        if self.macro_build != EnemyMacroBuild.StandardMacro:
            await self.chat_manager.chat_taunt_once(
                "EnemyBuild", lambda: "Tag:enemy_" + self.macro_build.name, team_only=True
            )

    @property
    def worker_rush_detected(self):
        return (
            self.rush_build == ExtendedEnemyRushBuild.WorkerRush
            or self.rush_build == ExtendedEnemyRushBuild.LateWorkerRush
        )

    def _set_rush(self, value: EnemyRushBuild):
        if value == ExtendedEnemyRushBuild.WorkerRush and self.ai.time > 60:
            value = ExtendedEnemyRushBuild.LateWorkerRush

        super()._set_rush(value)

    def _zerg_rushes(self):
        super()._zerg_rushes()
        if self.rush_build == ExtendedEnemyRushBuild.Macro:
            if self.cache.enemy(UnitTypeId.HATCHERY).closer_than(50, self.ai.start_location):
                # noinspection PyTypeChecker
                self._set_rush(ExtendedEnemyRushBuild.ProxyHatchery)
