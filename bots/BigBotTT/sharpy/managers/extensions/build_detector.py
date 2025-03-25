import enum
import sys
from typing import Dict, List, TYPE_CHECKING

from sc2.data import Race
from sharpy.interfaces import IEnemyUnitsManager
from sharpy.managers.core.manager_base import ManagerBase
from sharpy.managers.extensions.chat_manager import ChatManager

if TYPE_CHECKING:
    from sharpy.managers.core import *

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

townhall_start_types = {
    UnitTypeId.NEXUS,
    UnitTypeId.HATCHERY,
    UnitTypeId.COMMANDCENTER,
}


class EnemyRushBuild(enum.IntEnum):
    Macro = 0
    WorkerRush = 1
    # terran
    ProxyRax = 2
    Marauders = 3
    OneBaseRax = 4
    ProxyZealots = 5
    Marine = 6
    MassMarine = 7
    # protoss
    ProxyRobo = 8
    RoboRush = 9
    AdeptRush = 10
    CannonRush = 11
    Zealots = 12
    FreGate = 13
    # zerg
    PoolFirst = 14
    Pool12 = 15
    OneHatcheryAllIn = 16
    RoachRush = 17
    HatchPool15_14 = 18

"""class EnemyOpenningBuild(enum.IntEnum):
    # ZERG
    OpenningMacro = 0
    OpenningZerg = 1
    OpenningRoachZerg = 2
    # TERRAN
    OpenningBioTerran = 3
    OpenningMechTerran = 4
    OpenningAirTerran = 5
    # PROTOSS
    OpenningMassStalkerProtoss = 6
    OpenningDefenceOneBaseProtoss = 7
    OpenningProtoss = 8
"""
class EnemyMacroBuild(enum.IntEnum):
    # ZERG
    StandartMacro = 0
    EarlyZerg = 1
    EarlyRoachZerg = 2
    # TERRAN
    EarlyBioTerran = 3
    EarlyMechTerran = 4
    EarlyAirTerran = 5
    # PROTOSS
    EarlyMassStalkerProtoss = 6
    EarlyProtoss = 7

class EnemyMidBuild(enum.IntEnum):
    # ZERG
    MidMacro = 0
    MidAirZerg = 1
    MidHydraZerg = 2
    MidRoachZerg = 8
    # PROTOSS
    MidProtoss = 3
    MidAirProtoss = 4
    # TERRAN
    MidBioTerran = 5
    MidMechTerran = 6
    MidAirTerran = 7

class EnemyLateBuild(enum.IntEnum):
    # ZERG
    LateMacro = 0
    LateAirZerg = 1
    LatePowerZerg = 2
    LateRoachZerg = 8
    # PROTOSS
    LateProtoss = 3
    LateAirProtoss = 4
    # TERRAN
    LateBioTerran = 5
    LateMechTerran = 6
    LateAirTerran = 7
    
    

class BuildDetector(ManagerBase):
    """Enemy build detector."""

    enemy_units_manager: IEnemyUnitsManager
    chat_manager: ChatManager

    def __init__(self):
        super().__init__()
        self.rush_build = EnemyRushBuild.Macro
        self.macro_build = EnemyMacroBuild.StandartMacro
        self.mid_build = EnemyMidBuild.MidMacro
        self.late_build = EnemyLateBuild.LateMacro

        # Dictionary of unit or structure types that have been handled. tag is key
        # Note that snapshots of units / structures have a different tag.
        # Only visible buildings should be handled
        self.handled_unit_tags: Dict[int, UnitTypeId] = dict()
        # Timings when the unit was first seen or our estimate when structure was started building
        self.timings: Dict[UnitTypeId, List[float]] = dict()

    async def start(self, knowledge: "Knowledge"):
        # Just put them all her in order to avoid any issues with random enemy types
        self.chat_manager = knowledge.get_required_manager(ChatManager)
        if knowledge.ai.enemy_race == Race.Terran:
            self.timings[UnitTypeId.COMMANDCENTER] = [0]
        elif knowledge.ai.enemy_race == Race.Protoss:
            self.timings[UnitTypeId.NEXUS] = [0]
        elif knowledge.ai.enemy_race == Race.Zerg:
            self.timings[UnitTypeId.HATCHERY] = [0]
        elif knowledge.ai.enemy_race == Race.Random:
            self.timings[UnitTypeId.COMMANDCENTER] = [0]
            self.timings[UnitTypeId.NEXUS] = [0]
            self.timings[UnitTypeId.HATCHERY] = [0]

        await super().start(knowledge)

        self.enemy_units_manager = knowledge.get_required_manager(IEnemyUnitsManager)

    @property
    def rush_detected(self):
        return self.rush_build != EnemyRushBuild.Macro

    @property
    def worker_rush_detected(self):
        return self.rush_build == EnemyRushBuild.WorkerRush

    async def update(self):
        self._update_timings()
        self._rush_detection()
        self._build_detection()
        self._mid_detection()
        self._late_detection()
        await super().update()

        if self.macro_build != EnemyMacroBuild.StandartMacro:
            await self.chat_manager.chat_taunt_once(
                "EnemyBuild", lambda: "Tag:BotVS" + self.macro_build.name, team_only=True
            )
        if self.mid_build != EnemyMidBuild.MidMacro:
            await self.chat_manager.chat_taunt_once(
                "EnemyMid", lambda: "Tag:BotVS" + self.mid_build.name, team_only=True
            )
        if self.late_build != EnemyLateBuild.LateMacro:
            await self.chat_manager.chat_taunt_once(
                "EnemyLate", lambda: "Tag:BotVS" + self.mid_build.name, team_only=True
            )
        # if self.own_units_manager.unit_cache(UnitTypeId.ZERGLING):
        #     await self.chat_manager.chat_taunt_once(
        #         "OwnZergling", lambda: "Tag:U_zergling", team_only=True
        #     )

    def _update_timings(self):
        # Let's update just seen structures for now
        for unit in self.ai.enemy_structures:
            if unit.is_snapshot:
                continue

            if unit.tag not in self.handled_unit_tags or self.handled_unit_tags.get(unit.tag) != unit.type_id:
                self.handled_unit_tags[unit.tag] = unit.type_id

                if self.is_first_townhall(unit):
                    continue  # Don't add it to timings

                real_type = self.real_type(unit.type_id)
                list = self.timings.get(real_type, None)
                if not list:
                    list = []
                    self.timings[real_type] = list

                start_time = self.unit_values.building_start_time(self.ai.time, real_type, unit.build_progress)
                list.append(start_time)

    def started(self, type_id: UnitTypeId, index: int = 0) -> float:
        """ Returns an absurdly large number when the building isn't started yet"""
        list = self.timings.get(type_id, None)
        if not list:
            return sys.float_info.max
        if len(list) > index:
            return list[index]
        return sys.float_info.max

    def is_first_townhall(self, structure: Unit) -> bool:
        """Returns true if the structure is the first townhall for a player."""
        # note: this does not handle a case if Terran flies its first CC to another position
        return (
            structure.position == self.zone_manager.enemy_start_location and structure.type_id in townhall_start_types
        )

    async def post_update(self):
        if self.debug:
            if self.rush_build != EnemyRushBuild.Macro:
                msg = f"Enemy build: {self.rush_build.name}"
            else:
                msg = f"Enemy build: {self.macro_build.name}"

            if hasattr(self.ai, "plan"):
                build_order = self.ai.plan
                if hasattr(build_order, "orders"):
                    plan = build_order.orders[0]
                    if hasattr(plan, "response"):
                        msg += f"\nOwn build: {plan.response.name}"
                    else:
                        msg += f"\nOwn build: {type(plan).__name__}"
            self.client.debug_text_2d(msg, Point2((0.75, 0.15)), None, 14)

    def _set_rush(self, value: EnemyRushBuild):
        if self.rush_build == value:
            # Trying to set the value to what it already was, skip.
            return
        self.rush_build = value
        self.print(f"POSSIBLE RUSH: {value.name}.")

    def _rush_detection(self):
        if self.ai.time > 180:
            # Past three minutes, early rushes no longer relevant
            return

        if self.rush_build == EnemyRushBuild.WorkerRush:
            # Worker rush can never change to anything else
            return

        workers_close = self.cache.enemy_workers.filter(
            lambda u: u.distance_to(self.ai.start_location) < u.distance_to(self.zone_manager.enemy_start_location)
        )

        if workers_close.amount > 9:
            self._set_rush(EnemyRushBuild.WorkerRush)

        if self.knowledge.enemy_race == Race.Zerg:
            self._zerg_rushes()

        if self.knowledge.enemy_race == Race.Terran:
            self._terran_rushes()

        if self.knowledge.enemy_race == Race.Protoss:
            self._protoss_rushes()

    def _protoss_rushes(self):
        if len(self.cache.enemy(UnitTypeId.NEXUS)) > 1:
            self._set_rush(EnemyRushBuild.Macro)
            return  # enemy has expanded, no rush detection
        only_nexus_seen = False

        for enemy_nexus in self.cache.enemy(UnitTypeId.NEXUS):  # type: Unit
            if enemy_nexus.position == self.zone_manager.enemy_main_zone.center_location:
                only_nexus_seen = True
            else:
                self._set_rush(EnemyRushBuild.Macro)
                return  # enemy has build expansion, no rush detection

        close_buildings = self.cache.enemy_in_range(self.ai.start_location, 80).structure
        if close_buildings:
            if close_buildings(UnitTypeId.ROBOTICSFACILITY):
                self._set_rush(EnemyRushBuild.ProxyRobo)
                return

        if self.ai.time < 125:
            # early game and we have seen enemy Nexus
            close_gateways = (
                self.ai.enemy_structures(UnitTypeId.GATEWAY)
                .closer_than(30, self.zone_manager.enemy_main_zone.center_location)
                .amount
            )
            core = self.ai.enemy_structures(UnitTypeId.CYBERNETICSCORE).exists

            gates = self.cache.enemy(UnitTypeId.GATEWAY).amount
            robos = self.cache.enemy(UnitTypeId.ROBOTICSFACILITY).amount
            gas = self.cache.enemy(UnitTypeId.ASSIMILATOR).amount

            if self.ai.time > 110 and close_gateways == 0 and not core and only_nexus_seen:
                self._set_rush(EnemyRushBuild.ProxyZealots)

            if gates > 2:
                if gas == 2:
                    self._set_rush(EnemyRushBuild.FreGate)
                elif gas == 1:
                    self._set_rush(EnemyRushBuild.AdeptRush)
                elif gas == 0:
                    self._set_rush(EnemyRushBuild.Zealots)
            elif gates + robos > 2:
                self._set_rush(EnemyRushBuild.RoboRush)
            if self.ai.enemy_structures(UnitTypeId.FORGE).exists:
                self._set_rush(EnemyRushBuild.CannonRush)

    def _terran_rushes(self):
        only_cc_seen = False

        for enemy_cc in self.cache.enemy(
            [UnitTypeId.COMMANDCENTER, UnitTypeId.ORBITALCOMMAND, UnitTypeId.PLANETARYFORTRESS]
        ):  # type: Unit
            if enemy_cc.position == self.zone_manager.enemy_main_zone.center_location:
                only_cc_seen = True
            else:
                return self._set_rush(EnemyRushBuild.Macro)  # enemy has expanded, no rush detection

        if self.ai.time < 120:
            # early game and we have seen enemy CC
            close_barracks = (
                self.ai.enemy_structures(UnitTypeId.BARRACKS)
                .closer_than(30, self.zone_manager.enemy_main_zone.center_location)
                .amount
            )

            barracks = self.ai.enemy_structures(UnitTypeId.BARRACKS).amount
            factories = self.ai.enemy_structures(UnitTypeId.FACTORY).amount
            starposts = self.ai.enemy_structures(UnitTypeId.STARPORT).amount

            if (
                self.ai.enemy_structures(UnitTypeId.BARRACKSTECHLAB).amount == barracks
                and barracks >= 1
                and factories == 0
            ):
                return self._set_rush(EnemyRushBuild.Marauders)
            
            if (
                self.ai.enemy_structures(UnitTypeId.BARRACKSREACTOR).amount == barracks
                and barracks >= 2
                and factories == 0
            ):
                return self._set_rush(EnemyRushBuild.Marine)
            
            if (
                self.ai.enemy_structures(UnitTypeId.BARRACKSREACTOR).amount == barracks
                and barracks >= 5
            ):
                return self._set_rush(EnemyRushBuild.MassMarine)

            if self.ai.time > 110 and close_barracks == 0 and factories == 0 and only_cc_seen:
                return self._set_rush(EnemyRushBuild.ProxyRax)

            if barracks + factories > 2:
                return self._set_rush(EnemyRushBuild.OneBaseRax)

    def _zerg_rushes(self):
        hatcheries: Units = self.cache.enemy(UnitTypeId.HATCHERY)
        if len(hatcheries) > 2 or self.enemy_units_manager.enemy_worker_count > 28:
            # enemy has expanded TWICE or has large amount of workers, that's no rush
            return self._set_rush(EnemyRushBuild.Macro)

        if self.building_started_before(UnitTypeId.ROACHWARREN, 130) or (
            self.ai.time < 160 and self.cache.enemy(UnitTypeId.ROACH)
        ):
            return self._set_rush(EnemyRushBuild.RoachRush)

    """def _openning_detection(self):
        if self.openning_build != EnemyOpenningBuild.OpenningMacro:
            # Only set macro build once
            return

        if self.knowledge.enemy_race == Race.Zerg:
            if (self.ai.enemy_structures(UnitTypeId.HATCHERY).amount > 2
                or self.ai.enemy_units(UnitTypeId.ZERGLING).amount > 6
                or self.ai.enemy_units(UnitTypeId.QUEEN).amount > 2
            ):
                self.macro_build = EnemyMacroBuild.EarlyZerg
            if (self.ai.enemy_structures(UnitTypeId.ROACHWARREN).amount == 1
                or self.ai.enemy_structures(UnitTypeId.EXTRACTOR).amount > 2
                or self.ai.enemy_units(UnitTypeId.ROACH).amount > 2
            ):
                self.macro_build = EnemyMacroBuild.EarlyRoachZerg

        if self.knowledge.enemy_race == Race.Terran:
            if (self.ai.enemy_structures(UnitTypeId.BARRACKS).amount == 3):
                self.macro_build = EnemyMacroBuild.EarlyBioTerran
            if (self.ai.enemy_structures(UnitTypeId.FACTORY).amount == 2):
                self.macro_build = EnemyMacroBuild.EarlyMechTerran
            if (self.ai.enemy_structures(UnitTypeId.STARPORT).amount == 2):
                self.macro_build = EnemyMacroBuild.EarlyAirTerran

        if self.knowledge.enemy_race == Race.Protoss:
            if (self.ai.enemy_structures(UnitTypeId.NEXUS).amount == 1
                and self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 3
            ):
                self.macro_build = EnemyMacroBuild.EarlyDefenceOneBaseProtoss
            if (self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 3
                or self.ai.enemy_units(UnitTypeId.STALKER).amount > 5
            ):
                self.macro_build = EnemyMacroBuild.EarlyMassStalkerProtoss
            if (self.ai.enemy_structures(UnitTypeId.NEXUS).amount > 2
                or self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 2
                or self.ai.enemy_structures(UnitTypeId.CYBERNETICSCORE).amount == 1
            ):
                self.macro_build = EnemyMacroBuild.EarlyProtoss

        if self.openning_build != EnemyOpenningBuild.OpenningMacro:
            self.print(f"Enemy early build recognized as {self.openning_build.name}")
"""
    def _build_detection(self):
        if self.macro_build != EnemyMacroBuild.StandartMacro:
            # Only set macro build once
            return

        if self.knowledge.enemy_race == Race.Zerg:
            if (self.ai.enemy_structures(UnitTypeId.HATCHERY).amount > 2
                or self.ai.enemy_units(UnitTypeId.ZERGLING).amount > 6
                or self.ai.enemy_units(UnitTypeId.QUEEN).amount > 2
            ):
                self.macro_build = EnemyMacroBuild.EarlyZerg
            if (self.ai.enemy_structures(UnitTypeId.ROACHWARREN).amount == 1
                or self.ai.enemy_structures(UnitTypeId.EXTRACTOR).amount > 2
                or self.ai.enemy_units(UnitTypeId.ROACH).amount > 2
            ):
                self.macro_build = EnemyMacroBuild.EarlyRoachZerg

        if self.knowledge.enemy_race == Race.Terran:
            if (self.ai.enemy_structures(UnitTypeId.BARRACKS).amount > 3
                or self.ai.enemy_units(UnitTypeId.MARINE).amount > 6
            ):
                self.macro_build = EnemyMacroBuild.EarlyBioTerran
            if (self.ai.enemy_structures(UnitTypeId.FACTORY).amount > 2
                or self.ai.enemy_units(UnitTypeId.CYCLONE).amount > 2
                or self.ai.enemy_units(UnitTypeId.SIEGETANK).amount > 4
            ):
                self.macro_build = EnemyMacroBuild.EarlyMechTerran
            if (self.ai.enemy_structures(UnitTypeId.STARPORT).amount > 2
                or self.ai.enemy_units(UnitTypeId.BANSHEE).amount > 2
            ):
                self.macro_build = EnemyMacroBuild.EarlyAirTerran

        if self.knowledge.enemy_race == Race.Protoss:
            if (self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 4
                or self.ai.enemy_units(UnitTypeId.STALKER).amount > 5
            ):
                self.macro_build = EnemyMacroBuild.EarlyMassStalkerProtoss
            if (self.ai.enemy_structures(UnitTypeId.NEXUS).amount > 2
                and self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 2
                and self.ai.enemy_structures(UnitTypeId.CYBERNETICSCORE).amount == 1
            ):
                self.macro_build = EnemyMacroBuild.EarlyProtoss

        if self.macro_build != EnemyMacroBuild.StandartMacro:
            self.print(f"Enemy early build recognized as {self.macro_build.name}")

    def _mid_detection(self):
        if self.mid_build != EnemyMidBuild.MidMacro:
            # Only set macro build once
            return

        if self.knowledge.enemy_race == Race.Zerg:
            if (self.ai.enemy_structures(UnitTypeId.SPIRE).amount > 1
                and self.ai.enemy_structures(UnitTypeId.EXTRACTOR).amount > 3
                or self.ai.enemy_units(UnitTypeId.MUTALISK).amount > 3
            ):
                self.mid_build = EnemyMidBuild.MidAirZerg
            if (self.ai.enemy_structures(UnitTypeId.HATCHERY).amount > 3
                or self.ai.enemy_structures(UnitTypeId.HYDRALISKDEN).amount > 1
                or self.ai.enemy_units(UnitTypeId.HYDRALISK).amount > 4
            ):
                self.mid_build = EnemyMidBuild.MidHydraZerg
            if (
                self.ai.enemy_units(UnitTypeId.ROACH).amount > 12
            ):
                self.mid_build = EnemyMidBuild.MidRoachZerg

        if self.knowledge.enemy_race == Race.Terran:
            if (self.ai.enemy_structures(UnitTypeId.BARRACKS).amount > 6
                or self.ai.enemy_units(UnitTypeId.MARINE).amount > 15
            ):
                self.mid_build = EnemyMidBuild.MidBioTerran
            if (self.ai.enemy_structures(UnitTypeId.FACTORY).amount > 3
                or self.ai.enemy_units(UnitTypeId.CYCLONE).amount > 6
                or self.ai.enemy_units(UnitTypeId.SIEGETANK).amount > 8
            ):
                self.mid_build = EnemyMidBuild.MidMechTerran
            if (self.ai.enemy_structures(UnitTypeId.STARPORT).amount > 3
                or self.ai.enemy_units(UnitTypeId.BANSHEE).amount > 4
                or self.ai.enemy_units(UnitTypeId.BATTLECRUISER).amount > 2
            ):
                self.mid_build = EnemyMidBuild.MidAirTerran

        if self.knowledge.enemy_race == Race.Protoss:
            if (self.ai.enemy_structures(UnitTypeId.ROBOTICSFACILITY).amount > 1
                or self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 6
                or self.ai.enemy_structures(UnitTypeId.NEXUS).amount == 3
            ):
                self.mid_build = EnemyMidBuild.MidProtoss
            if (self.ai.enemy_structures(UnitTypeId.STARGATE).amount > 3
                or self.ai.enemy_units(UnitTypeId.VOIDRAY).amount > 4
            ):
                self.mid_build = EnemyMidBuild.MidAirProtoss

        if self.mid_build != EnemyMidBuild.MidMacro:
            self.print(f"Enemy mid build recognized as {self.mid_build.name}")

    def _late_detection(self):
        if self.late_build != EnemyLateBuild.LateMacro:
            # Only set macro build once
            return

        if self.knowledge.enemy_race == Race.Zerg:
            if (self.ai.enemy_units(UnitTypeId.MUTALISK).amount > 20
            ):
                self.late_build = EnemyLateBuild.LateAirZerg
            if (self.ai.enemy_units(UnitTypeId.ULTRALISKCAVERN).amount > 1
                or self.ai.enemy_units(UnitTypeId.INFESTOR).amount > 1
                or self.ai.enemy_units(UnitTypeId.LURKERMP).amount > 1
            ):
                self.late_build = EnemyLateBuild.LatePowerZerg
            if (
                self.ai.enemy_units(UnitTypeId.ROACH).amount > 30
            ):
                self.late_build = EnemyLateBuild.LateRoachZerg

        if self.knowledge.enemy_race == Race.Terran:
            if (self.ai.enemy_structures(UnitTypeId.BARRACKS).amount > 10
                or self.ai.enemy_structures(UnitTypeId.COMMANDCENTER).amount > 4
            ):
                self.late_build = EnemyLateBuild.LateBioTerran
            if (self.ai.enemy_structures(UnitTypeId.FACTORY).amount > 5):
                self.late_build = EnemyLateBuild.LateMechTerran
            if (self.ai.enemy_structures(UnitTypeId.STARPORT).amount > 5):
                self.late_build = EnemyLateBuild.LateAirTerran

        if self.knowledge.enemy_race == Race.Protoss:
            if (self.ai.enemy_structures(UnitTypeId.ROBOTICSBAY).amount > 1
                or self.ai.enemy_structures(UnitTypeId.GATEWAY).amount > 10
                or self.ai.enemy_structures(UnitTypeId.NEXUS).amount > 4
            ):
                self.late_build = EnemyLateBuild.LateProtoss
            if (self.ai.enemy_structures(UnitTypeId.STARGATE).amount > 5
                or self.ai.enemy_structures(UnitTypeId.FLEETBEACON).amount > 1
                or self.ai.enemy_units(UnitTypeId.TEMPEST).amount > 2
                or self.ai.enemy_units(UnitTypeId.CARRIER).amount > 2
            ):
                self.late_build = EnemyLateBuild.LateAirProtoss

        if self.late_build != EnemyLateBuild.LateMacro:
            self.print(f"Enemy late build recognized as {self.late_build.name}")

    def building_started_before(self, type_id: UnitTypeId, start_time_ceiling: int) -> bool:
        """Returns true if a building of type type_id has been started before start_time_ceiling seconds."""
        for unit in self.cache.enemy(type_id):  # type: Unit
            # fixme: for completed buildings this will report a time later than the actual start_time.
            # not fatal, but may be misleading.
            start_time = self.unit_values.building_start_time(self.ai.time, unit.type_id, unit.build_progress)
            if start_time is not None and start_time < start_time_ceiling:
                return True

        return False
