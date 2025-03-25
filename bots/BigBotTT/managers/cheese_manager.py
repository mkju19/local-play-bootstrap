from typing import Dict, List

from managers import StateAnalyzer
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit
from sharpy.managers import ManagerBase
from sharpy.managers.core.roles import UnitTask


class CheeseManager(ManagerBase):
    state_analyzer: StateAnalyzer

    def __init__(self) -> None:
        super().__init__()
        self.target_dict: Dict[int, List[int]] = {}
        self.activated = False

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.state_analyzer = knowledge.get_required_manager(StateAnalyzer)

    async def update(self):
        if self.ai.time > 3 * 60:
            return  # Cheese time is over

        if self.activated:
            self.do_micro()
        else:
            units = self.zone_manager.expansion_zones[0].known_enemy_units
            if not self.state_analyzer.natural_siege_ready:
                units.extend(self.zone_manager.expansion_zones[1].known_enemy_units)
            if units.structure:
                self.activated = True
                self.do_micro()

    def do_micro(self):
        units = self.zone_manager.expansion_zones[0].known_enemy_units
        if not self.state_analyzer.natural_siege_ready:
            units.extend(self.zone_manager.expansion_zones[1].known_enemy_units)

        for enemy in units:
            if self.unit_values.is_worker(enemy):
                self.ensure_chasers(enemy, 1)
            elif enemy.type_id == UnitTypeId.PHOTONCANNON:
                self.ensure_chasers(enemy, 2)
            elif enemy.type_id == UnitTypeId.PYLON:
                self.ensure_chasers(enemy, 4)
            elif enemy.type_id == UnitTypeId.BUNKER:
                self.ensure_chasers(enemy, 3)
            elif enemy.type_id == UnitTypeId.ENGINEERINGBAY:
                self.ensure_chasers(enemy, 3)
            elif enemy.type_id == UnitTypeId.HATCHERY:
                self.ensure_chasers(enemy, 5)

    async def post_update(self):
        pass

    def ensure_chasers(self, enemy: Unit, number: int):
        chasers: List[int] = self.target_dict.get(enemy.tag, [])
        for i in range(len(chasers), number):
            workers = self.roles.get_types_from({self.unit_values.my_worker_type}, UnitTask.Gathering)
            if workers:
                worker = workers.closest_to(enemy)
                chasers.append(worker.tag)
                self.roles.set_task(UnitTask.Reserved, worker)

        self.target_dict[enemy.tag] = chasers

        remove: List[int] = []

        for tag in chasers:
            worker = self.cache.by_tag(tag)
            if worker is None:
                remove.append(tag)
            else:
                worker.attack(enemy)
                self.roles.set_task(UnitTask.Reserved, worker)

        for tag in remove:
            chasers.remove(tag)
