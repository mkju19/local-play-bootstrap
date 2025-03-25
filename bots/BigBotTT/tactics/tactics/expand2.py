from sharpy.general.zone import Zone
from sharpy.managers.core import PathingManager
from sharpy.plans.acts import Expand
from sharpy.plans.acts.expand import train_worker_abilitites
from sharpy.sc2math import to_new_ticks


class Expand2(Expand):
    last_iteration_moved: int

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.last_iteration_moved = 0
        self.pather = knowledge.get_required_manager(PathingManager)

    def possibly_move_worker(self, zone: Zone):
        if not self.priority:
            return
        position = zone.center_location
        worker = self.get_worker_builder(position, self.builder_tag)
        if worker is None:
            return

        d = self.pather.walk_distance(worker.position, position)
        time = d / to_new_ticks(worker.movement_speed)
        available_minerals = self.ai.minerals - self.knowledge.reserved_minerals

        if self.last_iteration_moved >= self.knowledge.iteration - 1:
            # stop indecisiveness
            available_minerals += 50

        unit = self.ai._game_data.units[self.townhall_type.value]
        cost = self.ai._game_data.calculate_ability_cost(unit.creation_ability)

        if self.income_calculator.mineral_income > 0 and self.consider_worker_production:
            for town_hall in self.ai.townhalls:  # type: Unit
                # TODO: Zerg(?)
                if town_hall.orders:
                    starting_next_worker_in = -50 / self.income_calculator.mineral_income
                    for order in town_hall.orders:  # type: UnitOrder
                        if order.ability.id in train_worker_abilitites:
                            starting_next_worker_in += 12 * (1 - order.progress)

                    if starting_next_worker_in < time:
                        available_minerals -= 50  # should start producing workers soon now
                else:
                    available_minerals -= 50  # should start producing workers soon now

        if available_minerals + time * self.income_calculator.mineral_income >= cost.minerals:
            # Go wait
            self.set_worker(worker)
            self.last_iteration_moved = self.knowledge.iteration
            worker.move(position)
