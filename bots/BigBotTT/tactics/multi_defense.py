from typing import List, Union

from sharpy.general.zone import Zone
from sharpy.combat import MoveType
from sharpy.plans.acts import ActBase
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

from sharpy.knowledges import Knowledge, KnowledgeBot

from sharpy.managers.core.roles import UnitTask
from sharpy.general.extended_power import ExtendedPower
from sc2.units import Units

ZONE_CLEAR_TIMEOUT = 3


class ZoneDefense:
    def __init__(self, knowledge: Knowledge, zone: Zone) -> None:
        # noinspection PyTypeChecker
        self.ai: KnowledgeBot = knowledge.ai
        self.roles = knowledge.roles
        self.knowledge = knowledge
        self.active = False
        self.defender_tags: List[int] = []
        self.defender_worker_tags: List[int] = []
        self.defender_secondary_tags: List[int] = []
        self.zone_seen_enemy: float = 0
        self.own_power: ExtendedPower = ExtendedPower(knowledge.unit_values)
        self.enemy_power: ExtendedPower = ExtendedPower(knowledge.unit_values)
        self.defense_required: ExtendedPower = ExtendedPower(knowledge.unit_values)
        self.units: Units = Units([], knowledge.ai)
        self.enemies: Units = Units([], knowledge.ai)
        self.enemy_center: Point2 = Point2((0, 0))
        self.zone = zone

    def release(self):
        """ Releases all held defense units """
        self.active = False
        tags = self.defender_tags + self.defender_worker_tags + self.defender_secondary_tags
        for tag in tags:
            self.ai.roles.clear_task(tag)

        self.defender_tags.clear()
        self.defender_worker_tags.clear()
        self.defender_secondary_tags.clear()

        self.clear()

    def clear(self):
        """ Clears calculated data for new iteration"""
        self.enemy_power.clear()
        self.own_power.clear()
        self.units.clear()
        self.defense_required.clear()

    def is_defense_enough(self) -> bool:
        return self.own_power.is_enough_for(self.enemy_power)

    def add(self, unit: Unit, is_defender: bool):
        self.own_power.add_unit(unit)
        self.units.append(unit)
        self.remove_tag(unit)

        if is_defender:
            self.ai.roles.set_task(UnitTask.Defending, unit)
            self.defender_tags.append(unit.tag)
        else:
            self.ai.roles.set_task(UnitTask.Fighting, unit)
            self.defender_secondary_tags.append(unit.tag)

    def remove_tag(self, unit: Union[Unit, int]):
        if isinstance(unit, Unit):
            tag = unit.tag
        else:
            tag = unit

        if tag in self.defender_secondary_tags:
            self.defender_secondary_tags.remove(tag)
        if tag in self.defender_tags:
            self.defender_tags.remove(tag)

    def add_worker(self, unit: Unit):
        self.own_power.add_unit(unit)
        self.units.append(unit)
        self.roles.set_task(UnitTask.Defending, unit)

        if unit.tag not in self.defender_worker_tags:
            self.defender_worker_tags.append(unit.tag)

    def remove_worker(self, unit: Unit):
        self.roles.clear_task(unit)

        if unit.tag not in self.defender_worker_tags:
            self.defender_worker_tags.remove(unit.tag)


class PlanMultiDefense(ActBase):
    ZONE_CLEAR_TIMEOUT = 3

    def __init__(self):
        super().__init__()
        self.zone_datas: List[ZoneDefense] = []

    async def start(self, knowledge: Knowledge):
        await super().start(knowledge)
        self.worker_type: UnitTypeId = knowledge.my_worker_type

        for i in range(0, len(self.zone_manager.expansion_zones)):
            self.zone_datas.append(ZoneDefense(knowledge, self.zone_manager.expansion_zones[i]))

    async def execute(self) -> bool:
        self.init_zones()
        self.select_hard_defenders()
        self.select_idle_defenders()
        self.execute_defense()
        return True

    def init_zones(self):
        for zone_data in self.zone_datas:
            zone = zone_data.zone
            zone_data.clear()

            if not zone.is_ours and zone != self.zone_manager.own_main_zone:
                zone_data.release()
                continue

            zone_data.clear()

            enemies = zone.assaulting_enemies

            if self.should_defend(enemies):
                zone_data.zone_seen_enemy = self.ai.time
            else:
                # Delay before removing defenses in case we just lost visibility of the enemies
                if (
                    zone.last_scouted_center == self.knowledge.ai.time
                    or zone_data.zone_seen_enemy + ZONE_CLEAR_TIMEOUT < self.ai.time
                ):

                    zone_data.release()
                    continue  # Zone is well under control.

            zone_data.active = True
            zone_data.enemies.extend(enemies)
            zone_data.enemy_power.add_units(enemies)

            zone_data.defense_required.add_power(zone_data.enemy_power)
            zone_data.defense_required.multiply(1.5)

            if enemies.exists:
                # enemy_center = zone.assaulting_enemies.center
                zone_data.enemy_center = enemies.closest_to(zone.center_location).position
            else:
                zone_data.enemy_center = zone.gather_point

            self.remove_extra_ground_units(zone_data)
            self.remove_extra_air_units(zone_data)

    def should_defend(self, assaulting_enemies: Units) -> bool:
        if not assaulting_enemies:
            return False
        if len(assaulting_enemies) == 1 and assaulting_enemies[0].type_id == UnitTypeId.PHOENIX:
            return False
        return True

    def remove_extra_ground_units(self, zone_data):
        if zone_data.defense_required.ground_presence == 0 and zone_data.defense_required.air_presence > 0:
            remove_tags = []
            for tag in zone_data.defender_tags:
                unit = self.cache.by_tag(tag)
                if unit and not self.unit_values.can_shoot_air(unit):
                    self.roles.clear_task(unit)
                    remove_tags.append(unit.tag)

            for tag in zone_data.defender_secondary_tags:
                unit = self.cache.by_tag(tag)
                if unit and not self.unit_values.can_shoot_air(unit):
                    self.roles.clear_task(unit)
                    remove_tags.append(unit.tag)

            for tag in remove_tags:
                zone_data.remove_tag(tag)

    def remove_extra_air_units(self, zone_data):
        if zone_data.defense_required.ground_presence > 0 and zone_data.defense_required.air_presence == 0:
            remove_tags = []
            for tag in zone_data.defender_tags:
                unit = self.cache.by_tag(tag)
                if unit and not self.unit_values.can_shoot_ground(unit):
                    self.roles.clear_task(unit)
                    remove_tags.append(unit.tag)

            remove_tags = []
            for tag in zone_data.defender_secondary_tags:
                unit = self.cache.by_tag(tag)
                if unit and not self.unit_values.can_shoot_ground(unit):
                    self.roles.clear_task(unit)
                    remove_tags.append(unit.tag)

            for tag in remove_tags:
                zone_data.remove_tag(tag)

    def select_hard_defenders(self):
        for zone_data in self.zone_datas:
            if not zone_data.active:
                continue

            all_defenders = self.roles.all_from_task(UnitTask.Defending)
            zone_defenders = all_defenders.tags_in(zone_data.defender_tags)

            for unit in zone_defenders:
                zone_data.add(unit, True)

            # TODO: Should we add units to defenders that are being warped in?

            if zone_data.is_defense_enough():
                continue

            defense_required = ExtendedPower(self.unit_values)
            defense_required.add_power(zone_data.defense_required)
            defense_required.substract_power(zone_data.own_power)

            possible_defenders = self.roles.get_defenders(defense_required, zone_data.enemy_center)
            for unit in possible_defenders:
                zone_data.add(unit, True)

            defense_required = ExtendedPower(self.unit_values)
            defense_required.add_power(zone_data.defense_required)
            defense_required.substract_power(zone_data.own_power)

            self.worker_defence(defense_required, zone_data)

    def select_idle_defenders(self):
        max_total_power = 0
        maxed_zone = None

        for zone_data in self.zone_datas:
            if not zone_data.active:
                continue

            if zone_data.enemy_power.power > max_total_power:
                maxed_zone = zone_data
                max_total_power = zone_data.enemy_power.power

            all_defenders = self.roles.all_from_task(UnitTask.Fighting)
            zone_defenders = all_defenders.tags_in(zone_data.defender_secondary_tags)

            for unit in zone_defenders:
                zone_data.add(unit, False)

        if maxed_zone:
            idle = self.roles.all_from_task(UnitTask.Idle)
            for unit in idle:  # type: Unit

                if maxed_zone.defense_required.ground_presence > 0 and maxed_zone.defense_required.air_presence == 0:
                    if not self.unit_values.can_shoot_ground(unit):
                        continue  # don't pull units that can't shoot ground

                if maxed_zone.defense_required.ground_presence == 0 and maxed_zone.defense_required.air_presence > 0:
                    if not self.unit_values.can_shoot_air(unit):
                        continue  # don't pull units that can't shoot air

                if self.unit_values.defense_value(unit.type_id) > 0.5:
                    maxed_zone.add(unit, False)

    def execute_defense(self):
        for zone_data in self.zone_datas:
            if not zone_data.active:
                continue

            self.roles.refresh_tasks(zone_data.units)
            self.combat.add_units(zone_data.units)
            self.combat.execute(zone_data.enemy_center, MoveType.SearchAndDestroy)

    def worker_defence(self, defense_required: ExtendedPower, zone_data: ZoneDefense):
        zone: Zone = zone_data.zone
        defenders: float = 0
        all_defenders: Units = self.roles.all_from_task(UnitTask.Defending)
        zone_worker_defenders: Units = all_defenders.tags_in(zone_data.defender_worker_tags)
        ground_enemies: Units = zone.known_enemy_units.not_flying

        if defense_required.power <= 0:
            # Free all workers from defending
            for worker in zone_worker_defenders:  # type Unit
                zone_data.remove_worker(worker)
            return

        # Enemy value on same level and not on ramp
        hostiles_inside = 0
        for unit in ground_enemies:
            if self.ai.get_terrain_height(unit.position) == self.ai.get_terrain_height(zone.center_location):
                hostiles_inside += self.unit_values.defense_value(unit.type_id)

        if self.ai.workers.amount >= self.ai.supply_used - 2:
            # Workers only, defend for everything
            if zone.our_units.filter(lambda u: u.is_structure and u.health_percentage > 0.6):
                # losing a building, defend for everything
                if ground_enemies(UnitTypeId.PHOTONCANNON):
                    # Don't overreact if it's a low ground cannon rush
                    # 2 per proba and 4 per cannon is optimal
                    defense_count_panic = defense_required.power * 0.75
                else:
                    defense_count_panic = defense_required.power * 1.3

                threshold = 8
            else:
                defense_count_panic = hostiles_inside * 1.3
                threshold = 6  # probably a worker fight?
        else:
            # We have other units besides workers?
            defense_count_panic = hostiles_inside * 0.8  # Rely on defenders advantage
            threshold = 16

        if ground_enemies.exists:
            closest = ground_enemies.closest_to(zone.center_location)
            killing_probes = closest.distance_to(zone.center_location) < 6
        else:
            # No ground enemies near workers. There could be eg. a banshee though.
            killing_probes = False

        # Loop currently defending workers
        for unit in zone_worker_defenders:
            if defenders > defense_count_panic or (unit.shield + unit.health < threshold and not killing_probes):
                self.roles.clear_task(unit)
                zone.go_mine(unit)
                zone_data.remove_worker(unit)
            else:
                defenders += self.unit_values.defense_value(self.worker_type)
                zone_data.add_worker(unit)

        if self.ai.time > 5 * 60 and not killing_probes and not self.knowledge.enemy_race == Race.Zerg:
            # late game and enemies aren't killing probes, go back to mining!
            return

        if defense_required.power < 1 and not killing_probes:
            return  # Probably a single scout, don't pull workers

        if zone.our_wall() and self.ai.time < 200:
            possible_defender_workers = self.ai.workers
        else:
            possible_defender_workers = zone.our_workers

        if defense_required.melee_power > defense_required.power * 0.75 and not killing_probes:
            # This is to protect against sending all units to defend against zealots and other melee units and just die
            defense_count_panic = defense_count_panic * 0.6

        # Get help from other workers
        # type of worker unit doesn't really matter here, add current worker defenders to defender count
        for worker in possible_defender_workers.tags_not_in(zone_data.defender_worker_tags):
            # Let's use ones with shield left
            if defenders < defense_count_panic and (worker.shield > 3 or killing_probes):
                zone_data.add_worker(worker)
                defenders += self.unit_values.defense_value(worker.type_id)

    async def debug_actions(self):
        index = 0
        for zone_data in self.zone_datas:
            for unit in zone_data.units:
                if unit:
                    text = f"Defending zone {index}"
                    self.client.debug_text_world(text, unit.position3d)
            index += 1
