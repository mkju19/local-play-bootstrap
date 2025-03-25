import random
from typing import List, Optional

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
from sc2.position import Point2
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
from sc2.units import Units
from tactics.dodge_ramp_attack import DodgeRampAttack

class MicroBanshees(GenericMicro):
    def __init__(self):
        super().__init__()

    def group_solve_combat(self, units: Units, current_command: Action) -> Action:
        return current_command

    def unit_solve_combat(self, unit: Unit, current_command: Action) -> Action:
        if self.move_type in {MoveType.DefensiveRetreat}:
            return current_command
        
        bc = unit
        health_to_jump = 90
        if self.engaged_power.air_power > 8:
            health_to_jump = 100

        if bc.health < health_to_jump and self.cd_manager.is_ready(bc.tag, AbilityId.MOVE_MOVE):
            zones = self.zone_manager.our_zones_with_minerals
            if zones:
                position = zones[0].behind_mineral_position_center
                self.cd_manager.used_ability(bc.tag, AbilityId.MOVE_MOVE)
                return Action(position, False, AbilityId.MOVE_MOVE)

        if not self.cd_manager.is_ready(bc.tag, AbilityId.MOVE_MOVE) and bc.health_percentage < 0.9:
            scvs: Units = self.knowledge.unit_cache.own(UnitTypeId.SCV)
            if len(scvs) > 10 and scvs.closest_distance_to(bc) < 20:
                # Stay put!
                return Action(bc.position, True)
            
        return super().unit_solve_combat(unit, current_command)

class CycloneBot(KnowledgeBot):
    def __init__(self):
        super().__init__("Rusty Locks")

    def configure_managers(self) -> Optional[List["ManagerBase"]]:
        self.combat.default_rules.unit_micros[UnitTypeId.BANSHEE] = MicroBanshees()
        # self.combat.default_rules.unit_micros[UnitTypeId.HELLION] = MicroHellion()
        self.build_detector = BuildDetector()
        self.client.game_step = 5
        return [self.build_detector, BuildDetector(), ChatManager()]

    async def create_plan(self) -> BuildOrder:
        buildings = [
            Step(Supply(13), GridBuilding(UnitTypeId.SUPPLYDEPOT, 1)),
            Step(Supply(16), Expand(2)),
            Step(Supply(18), GridBuilding(UnitTypeId.BARRACKS, 1)),
            BuildGas(1),
            Step(Supply(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 2)),
            Step(None, BuildGas(2), skip_until=UnitExists(UnitTypeId.MARINE, 2)),
            Step(None, GridBuilding(UnitTypeId.FACTORY, 1), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
            Step(None, BuildAddon(UnitTypeId.FACTORYREACTOR, UnitTypeId.FACTORY, 1)),
            BuildGas(4),
            Step(None, Expand(3)),
            Step(None, DefensiveBuilding(UnitTypeId.BUNKER, DefensePosition.Entrance, None, 2)),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 4)),
            Step(None, BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 4)),
            BuildGas(6),
            Step(None, GridBuilding(UnitTypeId.ARMORY, 2)),
            Step(None, Expand(4)),
            GridBuilding(UnitTypeId.ENGINEERINGBAY, 1),
            BuildGas(8),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 8)),
            BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 6),
            BuildAddon(UnitTypeId.STARPORTREACTOR, UnitTypeId.STARPORT, 2),
            Step(None, Expand(4)),
            Step(None, GridBuilding(UnitTypeId.STARPORT, 12)),
            BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 9),
            BuildAddon(UnitTypeId.STARPORTREACTOR, UnitTypeId.STARPORT, 3),
        ]

        upgrades = [
            Step(UnitReady(UnitTypeId.ARMORY, 1), Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL1)),
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL1),
            Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL2),
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL2),
            Tech(UpgradeId.TERRANSHIPWEAPONSLEVEL3),
            Tech(UpgradeId.TERRANVEHICLEANDSHIPARMORSLEVEL3),
        ]

        self.attack = DodgeRampAttack(40)

        worker_scout = Step(None, WorkerScout(), skip_until=UnitExists(UnitTypeId.SUPPLYDEPOT, 1))
        self.distribute_workers = DistributeWorkers(0)

        tactics = [
            MineOpenBlockedBase(),
            PlanCancelBuilding(),
            LowerDepots(),
            PlanZoneDefense(),
            worker_scout,
            Step(None, CallMule(50), skip=Time(5 * 60)),
            Step(None, CallMule(100), skip_until=Time(5 * 60)),
            Step(None, ScanEnemy(), skip_until=Time(5 * 60)),
            self.distribute_workers,
            Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
            ManTheBunkers(),
            Repair(),
            ContinueBuilding(),
            PlanZoneGatherTerran(),
            self.attack,
            PlanFinishEnemy(),
        ]

        return BuildOrder(
            Step(UnitExists(UnitTypeId.BARRACKS, 1), SequentialList(self.depots)),
            [
                Step(
                    UnitExists(UnitTypeId.COMMANDCENTER, 2),
                    MorphOrbitals(3),
                    skip_until=UnitReady(UnitTypeId.BARRACKS, 1),
                ),
                Step(None, MorphPlanetary(2), skip_until=UnitReady(UnitTypeId.ENGINEERINGBAY, 1)),
            ],
            [
                Step(None, ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 40)),
                Step(UnitExists(UnitTypeId.COMMANDCENTER, 3), ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 100),),
            ],
            upgrades,
            ActUnit(UnitTypeId.MARINE, UnitTypeId.BARRACKS, 30),
            TerranUnit(UnitTypeId.BANSHEE, 4, priority=True),
            TerranUnit(UnitTypeId.RAVEN, 2, priority=True),
            TerranUnit(UnitTypeId.BANSHEE),
            Step(
                UnitReady(UnitTypeId.STARPORTREACTOR, 1),
                TerranUnit(UnitTypeId.VIKINGFIGHTER, 6),
                skip_until=Minerals(250),
            ),
            Step(
                UnitReady(UnitTypeId.FACTORYREACTOR, 1),
                TerranUnit(UnitTypeId.HELLION, 6),
                skip_until=Minerals(150),
            ),
            Step(
                UnitReady(UnitTypeId.FACTORYREACTOR, 1),
                TerranUnit(UnitTypeId.HELLIONTANK, 60),
                skip_until=Minerals(300),
            ),
            buildings,
            SequentialList(tactics),
        )

    @property
    def depots(self) -> List[Step]:
        return [
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 1), None),
            Step(SupplyLeft(6), GridBuilding(UnitTypeId.SUPPLYDEPOT, 2)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 2), None),
            Step(SupplyLeft(14), GridBuilding(UnitTypeId.SUPPLYDEPOT, 4)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 4), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 6)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 5), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 7)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 6), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 10)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 8), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 12)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 10), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 14)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 13), None),
            Step(SupplyLeft(20), GridBuilding(UnitTypeId.SUPPLYDEPOT, 16)),
            Step(UnitReady(UnitTypeId.SUPPLYDEPOT, 16), GridBuilding(UnitTypeId.SUPPLYDEPOT, 20)),
        ]

class LadderBot(CycloneBot):
    @property
    def my_race(self):
        return Race.Terran
