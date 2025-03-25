import random

from chance.strats.strat import Strat
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sharpy.plans import BuildOrder, SequentialList, StepBuildGas, Step
from sharpy.plans.acts import *
from sharpy.plans.acts.terran import AutoDepot, MorphPlanetary, BuildAddon
from sharpy.plans.require import Any, Gas, UnitExists, TechReady
from sharpy.plans.tactics import *
from sharpy.plans.tactics.terran import LowerDepots, ManTheBunkers, Repair, ContinueBuilding, PlanZoneGatherTerran
from sharpy.utils import select_build_index
from sharpy.plans.acts.terran import *
from sharpy.plans.require import *
from sharpy.plans.tactics.terran import *


class JumpIn(ActBase):
    def __init__(self):
        self.done = False
        super().__init__()

    async def execute(self) -> bool:
        if self.done:
            return True
        bcs = self.cache.own(UnitTypeId.BATTLECRUISER)
        if bcs.amount > 1:
            self.done = True
            for bc in bcs:
                self.knowledge.cooldown_manager.used_ability(bc.tag, AbilityId.EFFECT_TACTICALJUMP)

                bc(AbilityId.EFFECT_TACTICALJUMP, self.zone_manager.enemy_main_zone.behind_mineral_position_center)

        return True

class MorphProxyPlanetary(MorphPlanetary):
    def __init__(self):
        super().__init__(1)

    async def execute(self) -> bool:
        target_count = self.cache.own(self.result_type).amount
        start_buildings = self.cache.own(self.building_type).ready.sorted_by_distance_to(
            self.knowledge.zone_manager.enemy_main_zone.center_location)

        for target in start_buildings:
            if target.orders and target.orders[0].ability.id == self.ability_type:
                target_count += 1

        if target_count >= self.target_count:
            return True

        for target in start_buildings:
            if target.is_ready:
                if self.knowledge.can_afford(self.ability_type):
                    target(self.ability_type)

                self.knowledge.reserve_costs(self.ability_type)
                target_count += 1

                if target_count >= self.target_count:
                    return True
        if start_buildings:
            return False
        return True


class PlanetaryFortressRush(Strat):
    jump: int

    async def create_plan(self) -> BuildOrder:
        self.build_name = "default"

        attack_value = random.randint(150, 200)
        self.attack = Step(None, PlanZoneAttack(attack_value))
        empty = BuildOrder([])

        if self.build_name == "default":
            self.jump = select_build_index(self._bot.knowledge, "build.bc", 0, 1)
        else:
            self.jump = int(self.build_name)

        if self.jump == 0:
            self._bot.knowledge.print(f"Att at {attack_value}", "Build")
        else:
            self._bot.knowledge.print(f"Jump, att at {attack_value}", "Build")
            

        worker_scout = Step(None, WorkerScout(), skip_until=UnitExists(UnitTypeId.SUPPLYDEPOT, 1))
        self.distribute_workers = DistributeWorkers(4)
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
            Step(None, JumpIn(), RequireCustom(lambda k: self.jump == 0)),
            self.attack,
            PlanFinishEnemy(),
        ]
        return BuildOrder([
            SequentialList([
                BuildPosition(UnitTypeId.COMMANDCENTER, self._bot.knowledge.zone_manager.enemy_natural.center_location,
                              exact=True, only_once=True),
                StepBuildGas(2),
                ActBuilding(UnitTypeId.ENGINEERINGBAY),
                ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 17),
                MorphProxyPlanetary(),
                ActBuilding(UnitTypeId.SUPPLYDEPOT, 1),
                BuildOrder(
                    empty.depots,
                    # ActUnit(UnitTypeId.SCV, UnitTypeId.PLANETARYFORTRESS, 5),
                    Step(None, MorphOrbitals(1), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
                    Step(None, MorphPlanetary(), skip_until=UnitReady(UnitTypeId.FACTORY, 1)),
                    SequentialList(
                        GridBuilding(UnitTypeId.BARRACKS, 1),
                        Step(UnitExists(UnitTypeId.PLANETARYFORTRESS, 1, include_killed=True), Expand(2)),
                        GridBuilding(UnitTypeId.SUPPLYDEPOT, 2),
                        Step(None, GridBuilding(UnitTypeId.FACTORY, 1), skip_until=UnitReady(UnitTypeId.BARRACKS, 1)),
                        Step(UnitReady(UnitTypeId.FACTORY, 1), GridBuilding(UnitTypeId.STARPORT, 1)),
                        DefensiveBuilding(UnitTypeId.BUNKER, DefensePosition.Entrance, 1),
                        Step(None, GridBuilding(UnitTypeId.BARRACKS, 2)),
                        BuildGas(3),
                        Step(None, BuildAddon(UnitTypeId.FACTORYTECHLAB, UnitTypeId.FACTORY, 1)),
                        Step(UnitReady(UnitTypeId.STARPORT, 1), GridBuilding(UnitTypeId.FUSIONCORE, 1)),
                        DefensiveBuilding(UnitTypeId.BUNKER, DefensePosition.Entrance, 1),
                        Step(None, BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 1)),
                        StepBuildGas(
                            4, None, UnitExists(UnitTypeId.BATTLECRUISER, 1, include_killed=True, include_pending=True)
                        ),
                        Step(None, BuildAddon(UnitTypeId.BARRACKSTECHLAB, UnitTypeId.BARRACKS, 1)),
                        Step(None, BuildAddon(UnitTypeId.BARRACKSREACTOR, UnitTypeId.BARRACKS, 1)),
                        Step(None, GridBuilding(UnitTypeId.STARPORT, 2)),
                        Step(
                            UnitReady(UnitTypeId.STARPORT, 2), BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 2),
                        ),
                        Step(None, Tech(UpgradeId.SHIELDWALL)),
                    ),
                    [Step(None, ActUnit(UnitTypeId.SCV, UnitTypeId.COMMANDCENTER, 90))],
                    [
                        Step(Minerals(600), Expand(8),),
                        BuildGas(10),
                        Step(Gas(600), GridBuilding(UnitTypeId.STARPORT, 6)),
                        Step(None, BuildAddon(UnitTypeId.STARPORTTECHLAB, UnitTypeId.STARPORT, 6),),
                    ],
                    [
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
                        Step(
                            UnitReady(UnitTypeId.STARPORT, 1), ActUnit(UnitTypeId.RAVEN, UnitTypeId.STARPORT, 2, priority=True),
                        ),
                    ],
                    Step(
                        None,
                        SequentialList(ActUnit(UnitTypeId.BATTLECRUISER, UnitTypeId.STARPORT, 20, priority=True)),
                        skip_until=UnitReady(UnitTypeId.FUSIONCORE, 1),
                    ),
                    ActUnit(UnitTypeId.SIEGETANK, UnitTypeId.FACTORY, 10),
                    ActUnit(UnitTypeId.MARINE, UnitTypeId.BARRACKS, 50),
                    SequentialList(tactics),
                ),
            ]),
        ])
