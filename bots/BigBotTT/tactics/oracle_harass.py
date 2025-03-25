from typing import List, Optional

from sharpy.interfaces import ICombatManager, IZoneManager
from sharpy.combat import MoveType
from sharpy.plans.acts import ActBase
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sharpy.general.zone import Zone
from sharpy.general.extended_power import ExtendedPower
from sharpy.knowledges import Knowledge
from sharpy.managers.core.roles import UnitTask


class PlanOracleHarass(ActBase):
    combat: ICombatManager
    zone_manager: IZoneManager
    enemy_turrets: Units
    target_zone: Zone

    def __init__(self):
        super().__init__()
        self.scout_tags: List[int] = []

        self.started = False
        self.retreat = False
        self.ended = False

        self.blacklisted_zones: List[Zone] = []

    async def start(self, knowledge: Knowledge):
        await super().start(knowledge)
        self.combat = knowledge.get_required_manager(ICombatManager)
        self.zone_manager = knowledge.get_required_manager(IZoneManager)

        self.target_zone: Zone = self.zone_manager.enemy_main_zone
        self.enemy_turrets = Units([], self.ai)

    async def execute(self) -> bool:
        if self.ended:
            return True  # Never block

        oracle: Unit
        if not self.started:
            await self.check_start()

        if self.started:
            oracles: Units = Units([], self.ai)
            for tag in self.scout_tags:
                oracle = self.cache.by_tag(tag)
                if oracle is not None:
                    oracles.append(oracle)
            if len(oracles) == 0:
                await self.end_scout()
            else:
                await self.micro_oracles(oracles)

        return True  # Never block

    async def micro_oracles(self, oracles: Units):
        self.enemy_turrets = self.ai.enemy_structures.of_type(
            [UnitTypeId.MISSILETURRET, UnitTypeId.BUNKER, UnitTypeId.PHOTONCANNON, UnitTypeId.SPORECRAWLER]
        ).ready

        target_position: Point2
        move: MoveType
        self.roles.set_tasks(UnitTask.Reserved, oracles)
        for oracle in oracles:  # type: Unit
            self.combat.add_unit(oracle)
            # Check retreat against turrets
            if self.enemy_turrets.exists and self.enemy_turrets.closest_distance_to(oracle.position) < 7:
                await self.start_retreat()
                continue

            # Check retreat against enemy army
            enemy_power = ExtendedPower(self.knowledge.unit_values)
            enemies = self.ai.enemy_units.closer_than(9, oracle)

            if enemies.exists:
                for enemy in enemies:
                    enemy_power.add_unit(enemy)
                # if enemy_power.air_power > 10:
                #     await self.start_retreat()
                #     continue

            # if self.target_position is None:
            #     self.combat.addUnit(oracle, self.zone_manager.own_main_zone.center_location, MoveType.PanicRetreat)
            # el
            if self.retreat and oracle.shield >= 55 and oracle.energy > 50:
                self.set_zone()
                if self.target_zone is not None:
                    self.target_position = await self.get_zone_target(self.target_zone, oracles.center)
                    if self.target_position is not None:
                        self.print("Retreat stopped.")
                        self.retreat = False
            elif (
                oracle.health * 0.25 + oracle.shield < 20
                or oracle.energy < 1
                or (oracle.energy < 30 and not oracle.has_buff(BuffId.ORACLEWEAPON))
            ):
                await self.start_retreat()

        if self.retreat:
            target_position = self.zone_manager.own_main_zone.center_location
            move = MoveType.PanicRetreat
        else:
            target_position = self.target_position
            move = MoveType.Harass

        self.combat.execute(target_position, move)

    async def start_retreat(self):
        if not self.retreat:
            self.print("Retreating.")
            self.retreat = True

        self.target_position = self.zone_manager.own_main_zone.center_location

    async def check_start(self):
        oracles = self.ai.units(UnitTypeId.ORACLE)
        if oracles.amount >= 1:
            self.set_zone()

            if self.target_zone is not None:
                self.target_position = await self.get_zone_target(self.target_zone, oracles.center)
                if self.target_position is not None:
                    self.print("Started.")
                    self.started = True

                    for oracle in oracles:
                        self.scout_tags.append(oracle.tag)
                        self.roles.set_tasks(UnitTask.Scouting, oracles)

    async def get_zone_target(self, zone: Zone, center) -> Optional[Point2]:
        target_position = await self.get_zone_closest(zone, center)

        if self.enemy_turrets.exists and self.enemy_turrets.closest_distance_to(target_position) < 10:
            target_position = await self.get_zone_furthest(zone, center)
            if self.enemy_turrets.closest_distance_to(target_position) < 10:
                self.blacklisted_zones.append(zone)
                self.print(f"blacklisting zone: {self.target_zone.center_location}.")
                return None

        return target_position

    def set_zone(self):
        self.print(f"selecting target zone.")
        for zone in self.zone_manager.enemy_expansion_zones:
            if zone not in self.blacklisted_zones:
                self.print(f"looking at zone {self.target_zone.center_location}.")
                if zone.is_enemys or zone.last_scouted_center + 30 < self.ai.time:
                    self.target_zone = zone
                    self.print(f"zone is {self.target_zone.center_location}.")
                    return

    async def get_zone_closest(self, zone: Zone, center) -> Point2:
        target_position = zone.behind_mineral_position_center  # default position
        if zone.mineral_fields.exists and len(zone.behind_mineral_positions) > 0:
            distance = 9999999

            for pos in zone.behind_mineral_positions:
                d2 = center.distance_to(pos)
                if d2 < 3.16:
                    self.is_behind_minerals = True
                if d2 < distance:
                    # Get closest position
                    target_position = pos
                    distance = d2

        return target_position

    async def get_zone_furthest(self, zone: Zone, center) -> Point2:
        target_position = zone.behind_mineral_position_center  # default position
        if zone.mineral_fields.exists and len(zone.behind_mineral_positions) > 0:
            distance = 0
            for pos in zone.behind_mineral_positions:
                d2 = center.distance_to(pos)
                if d2 > distance:
                    # Get furthest away position
                    target_position = pos
                    distance = d2

        return target_position

    async def end_scout(self):
        self.print("Ended.")
        self.started = False
        self.ended = True
        self.roles.clear_tasks(self.scout_tags)
        self.scout_tags.clear()
        self.is_behind_minerals = False
