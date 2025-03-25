from sharpy.plans.require.time import Time
import random
from typing import Dict, List, Optional

from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId
from sharpy.managers.extensions import BuildDetector, ChatManager
from sharpy.plans.acts import *
from sharpy.plans.acts.terran import *
from sharpy.plans.require import *
from sharpy.plans.require.supply import SupplyType
from sharpy.plans.tactics import *
from sharpy.plans.tactics.weak import *
from sharpy.plans.tactics.terran import *
from sharpy.plans import BuildOrder, Step, SequentialList, StepBuildGas
from sc2.ids.upgrade_id import UpgradeId
from sharpy.interfaces import IZoneManager, IGameAnalyzer, IEnemyUnitsManager
from sharpy.knowledges import Knowledge
from sharpy.combat import *
from sharpy.events import *
from sharpy.general import *
from sharpy.interfaces import *
from sharpy.knowledges.knowledge_bot import KnowledgeBot
from tactics.dodge_ramp_attack import DodgeRampAttack
from sharpy.combat import Action, MicroStep
from sc2.position import Point2
from sharpy.plans.if_else import IfElse
from typing import Optional
from sharpy.managers import *
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.units import Units
from sharpy.general.extended_power import ExtendedPower
from sharpy.general.zone import Zone
from sharpy.combat import MoveType
from sharpy.managers.core.roles import UnitTask
from sharpy.plans.tactics import PlanZoneAttack
from sc2.position import Point2
from sharpy.plans.tactics.zone_attack import AttackStatus
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.unit import Unit
from sharpy.knowledges import KnowledgeBot
from sharpy.utils import select_build_index
from sharpy.plans.tactics.terran.addon_swap import PlanAddonSwap, ExecuteAddonSwap

class MicroGhost(GenericMicro):
    def __init__(self):
        super().__init__()

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        self.model = CombatModel.StalkerToRoach
        return super().group_solve_combat(units, current_command)

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        bc = unit
        if self.cd_manager.is_ready(bc.tag, AbilityId.SNIPE_SNIPE):
            shuffler = unit.tag % 10
            best_score = 100  # Let's not waste yamato on marines or zerglings
            target: Optional[Unit] = None
            enemy: Unit

            for enemy in self.enemies_near_by:
                d = enemy.distance_to(unit)
                if d < 11 and self.unit_values.power(enemy) > 1:
                    score = enemy.health
                    # TODO: Needs proper target locking in order to not fire at the same target
                    # Simple and stupid way in an attempt to not use yamato gun on same target:
                    score += enemy.tag % (shuffler + 2)

                    if score > best_score:
                        target = enemy
                        best_score = score

            if target is not None:
                return Action(target, False, AbilityId.SNIPE_SNIPE)

        return super().unit_solve_combat(unit, current_command)
  
class MicroMarauder(GenericMicro):
    def __init__(self):
        super().__init__()

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        self.model = CombatModel.StalkerToRoach
        return super().group_solve_combat(units, current_command)

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command
        return super().unit_solve_combat(unit, current_command)

class MicroMarine(GenericMicro):
    def __init__(self):
        super().__init__()

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        self.model = CombatModel.StalkerToRoach
        return super().group_solve_combat(units, current_command)

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command
        return super().unit_solve_combat(unit, current_command)

class BuildBio(BuildOrder):
    zone_manager: IZoneManager

    def __init__(self):
        self.worker_rushed = False
        self.rush_bunker = BuildPosition(UnitTypeId.BUNKER, Point2((0, 0)), exact=True)

        warn = WarnBuildMacro(
            [
                (UnitTypeId.SUPPLYDEPOT, 1, 18),
                (UnitTypeId.BARRACKS, 1, 42),
                (UnitTypeId.REFINERY, 1, 44),
                (UnitTypeId.COMMANDCENTER, 2, 60 + 44),
                (UnitTypeId.BARRACKSREACTOR, 1, 120),
                (UnitTypeId.FACTORY, 1, 120 + 21),
                (UnitTypeId.STARPORT, 1, 120 + 21),
            ],
            [],
        )

        scv = [
            Step(None, TerranUnit(UnitTypeId.MARINE, 2, priority=True), skip_until=lambda k: self.worker_rushed),
            Step(None, MorphOrbitals(), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
            Step(
                None,
                ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 16 + 6),
                skip=UnitExists(UnitTypeId.COMMANDCENTER, 2),
            ),
            Step(None, ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 80)),
        ]

        dt_counter = [
            Step(
                Any(
                    [
                        EnemyBuildingExists(UnitTypeId.DARKSHRINE),
                        EnemyUnitExistsAfter(UnitTypeId.DARKTEMPLAR),
                        EnemyUnitExistsAfter(UnitTypeId.BANSHEE),
                    ]
                ),
                None,
            ),
            Step(None, GridBuilding(UnitTypeId.ENGINEERINGBAY, 1)),
            Step(None, DefensiveBuilding(UnitTypeId.MISSILETURRET, DefensePosition.Entrance, 2)),
            Step(None, DefensiveBuilding(UnitTypeId.MISSILETURRET, DefensePosition.CenterMineralLine, None)),
        ]

        dt_counter2 = [
            Step(
                Any(
                    [
                        EnemyBuildingExists(UnitTypeId.DARKSHRINE),
                        EnemyUnitExistsAfter(UnitTypeId.DARKTEMPLAR),
                        EnemyUnitExistsAfter(UnitTypeId.BANSHEE),
                    ]
                ),
                None,
            ),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 2)),
            Step(None, BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 1)),
            Step(UnitReady(UnitTypeId.STARPORT, 1), ActUnit(UnitTypeId.RAVEN, UnitTypeId.STARPORT, 2)),
        ]

        opener = [
            Step(Supply(13), GridBuilding(UnitTypeId.SUPPLYDEPOT, 1, priority=True)),
            GridBuilding(UnitTypeId.BARRACKS, 1, priority=True),
            StepBuildGas(1, Supply(15)),
            TerranUnit(UnitTypeId.REAPER, 1, only_once=True, priority=True),
            Step(
                None,
                Expand(2),
                skip_until=Any(
                    [
                        RequireCustom(lambda k: not self.rush_detected),
                        UnitExists(UnitTypeId.SIEGETANK, 2, include_killed=True),
                    ]
                ),
            ),
            Step(
                None,
                CancelBuilding(UnitTypeId.COMMANDCENTER, 1),
                skip=Any(
                    [
                        RequireCustom(lambda k: not self.rush_detected),
                        UnitExists(UnitTypeId.SIEGETANK, 2, include_killed=True),
                    ]
                ),
            ),
            Step(None, self.rush_bunker, skip_until=lambda k: self.rush_detected),
            Step(None, GridBuilding(UnitTypeId.BARRACKS, 2), skip_until=lambda k: self.rush_detected),
            GridBuilding(UnitTypeId.SUPPLYDEPOT, 2, priority=True),
            BuildAddon(UnitTypeId.BARRACKSTECHLAB, UnitTypeId.BARRACKS, 1),
            GridBuilding(UnitTypeId.FACTORY, 1),
        ]

        buildings = [
            Step(Supply(13), GridBuilding(UnitTypeId.SUPPLYDEPOT, 1)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 0.95), GridBuilding(UnitTypeId.BARRACKS, 1)),
            StepBuildGas(1, Supply(16)),
            Expand(2),
            Step(None, GridBuilding(UnitTypeId.FACTORY, 2), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
            Step(
                None,
                BuildAddon(UnitTypeId.FACTORYTECHLAB, UnitTypeId.FACTORY, 2),
                skip_until=UnitReady(UnitTypeId.FACTORY, 1),
            ),
            # AutoDepot(),
            BuildGas(2),
            Step(Supply(13), GridBuilding(UnitTypeId.SUPPLYDEPOT, 3)),
            BuildGas(3),
            Step(None, Expand(3)),
            Step(None, GridBuilding(UnitTypeId.FACTORY, 4), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
            Step(
                None,
                BuildAddon(UnitTypeId.FACTORYTECHLAB, UnitTypeId.FACTORY, 4),
                skip_until=UnitReady(UnitTypeId.FACTORY, 1),
            ),
            # BuildStep(None, GridBuilding(UnitTypeId.FACTORY, 3)),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 1)),
            Step(None, BuildAddon(UnitTypeId.STARPORTREACTOR, UnitTypeId.STARPORT, 1)),
            BuildGas(6),
            Step(None, GridBuilding(UnitTypeId.ARMORY, 2)),
            Step(None, GridBuilding(UnitTypeId.FUSIONCORE, 1)),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 6)),
            Step(None, BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 6)),
            Step(None, Expand(6),),
            BuildGas(20),
        ]

        tech = [
            Tech(UpgradeId.TERRANVEHICLEWEAPONSLEVEL1),
            Tech(UpgradeId.TERRANVEHICLEWEAPONSLEVEL2),
            Tech(UpgradeId.TERRANVEHICLEWEAPONSLEVEL3),
            Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL1),
            Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL2),
            Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL3),
            # TODO Fix me, doesn't work in python-sc2 and neither does here:
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL1),
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL2),
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL3),
        ]

        depots = [
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 3), None),
            Step(SupplyLeft(14), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 4),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 4), None),
            Step(SupplyLeft(16), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 6),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 4), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 7),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 6), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 9),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 7), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 10),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 7), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 12),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 10), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 14),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 12), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 16),),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 14), None),
            Step(SupplyLeft(20), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 20),),
            Step(Minerals(1000), DefensiveBuilding(UnitTypeId.SUPPLYDEPOT, DefensePosition.FarEntrance, 1, 40),),
        ]

        mech = [
            Step(None, TerranUnit(UnitTypeId.SIEGETANK, 30, priority=True)),
            Step(UnitReady(UnitTypeId.STARPORTTECHLAB, 1), TerranUnit(UnitTypeId.BATTLECRUISER, 20, priority=True)),
            Step(UnitReady(UnitTypeId.STARPORTREACTOR, 1), TerranUnit(UnitTypeId.VIKINGFIGHTER, 10)),
        ]

        use_money = BuildOrder(
            [
                Step(None, TerranUnit(UnitTypeId.SIEGETANK, 20, priority=True)),
                Step(UnitReady(UnitTypeId.STARPORTTECHLAB, 1), TerranUnit(UnitTypeId.BATTLECRUISER, 20, priority=True)),
                Step(UnitReady(UnitTypeId.STARPORTREACTOR, 1), TerranUnit(UnitTypeId.VIKINGFIGHTER, 10)),
            ]
        )

        use_money = BuildOrder(
            [
                Step(Gas(250), GridBuilding(UnitTypeId.STARPORT, 8)),
                Step(Gas(350), BuildAddon(UnitTypeId.STARPORTREACTOR, UnitTypeId.STARPORT, 6)),
            ]
        )

        super().__init__([depots, warn, scv, opener, buildings, dt_counter, dt_counter2, tech, mech, use_money])

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)
        self.build_detector = knowledge.get_required_manager(BuildDetector)
        self.rush_bunker.position = self.zone_manager.expansion_zones[0].ramp.ramp.barracks_in_middle

    @property
    def rush_detected(self) -> bool:
        return self.build_detector.rush_detected

    async def execute(self) -> bool:
        if not self.worker_rushed and self.ai.time < 120:
            self.worker_rushed = self.cache.enemy_workers.filter(
                lambda u: u.distance_to(self.ai.start_location) < u.distance_to(self.zone_manager.enemy_start_location)
            )

        return await super().execute()


class Banshees(KnowledgeBot):
    def __init__(self):
        super().__init__("Rusty Infantry")
        self.attack = DodgeRampAttack(160)

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)
        self.game_analyzer = knowledge.get_required_manager(IGameAnalyzer)
        self.enemy_units_manager = knowledge.get_required_manager(IEnemyUnitsManager)

    def configure_managers(self) -> Optional[List["ManagerBase"]]:
        self.combat.default_rules.unit_micros[UnitTypeId.MARINE] = MicroMarine()
        self.combat.default_rules.unit_micros[UnitTypeId.MARAUDER] = MicroMarauder()
        self.combat.default_rules.unit_micros[UnitTypeId.GHOST] = MicroGhost()
        # self.combat.default_rules.unit_micros[UnitTypeId.HELLION] = MicroHellion()
        self.build_detector = BuildDetector()
        self.client.game_step = 5
        return [self.build_detector, BuildDetector(), ChatManager()]

    async def create_plan(self) -> BuildOrder:
        self.knowledge.data_manager.set_build("bio")
        worker_scout = Step(None, WorkerScout(), skip_until=UnitExists(UnitTypeId.SUPPLYDEPOT, 1))
        tactics = [
            MineOpenBlockedBase(),
            PlanCancelBuilding(),
            LowerDepots(),
            PlanZoneDefense(),
            worker_scout,
            # AutoDepot(),
            Step(None, CallMule(50), skip=Time(5 * 60)),
            Step(None, CallMule(100), skip_until=Time(5 * 60)),
            Step(None, ScanEnemy(), skip_until=Time(5 * 60)),
            DistributeWorkers(),
            Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
            ManTheBunkers(),
            Repair(),
            ContinueBuilding(),
            PlanZoneGatherTerran(),
            Step(Gas(2000), DodgeRampAttack(160),),
            PlanFinishEnemy(),
        ]

        return BuildOrder([BuildBio(), tactics])


class LadderBot(Banshees):
    @property
    def my_race(self):
        return Race.Terran
