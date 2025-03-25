from math import floor, ceil

from sc2 import AbilityId, UnitTypeId
from tactics import Building


class AutoGate(Building):
    def __init__(self):
        self.desired_workers = 70
        super().__init__(UnitTypeId.GATEWAY, 1)

    @property
    def mineral_gather_rate(self) -> float:
        return self.income_calculator.mineral_income

    @property
    def vespene_gather_rate(self) -> float:
        return self.income_calculator.gas_income

    async def execute(self) -> bool:
        self.to_count = await self.gate_count_calc()
        self.desired_workers = self._optimal_worker_count()
        return await super().execute()

    def _optimal_worker_count(self) -> int:
        count = 1
        for townhall in self.ai.townhalls:  # type: Unit
            if townhall.is_ready:
                count += townhall.ideal_harvesters
            else:
                count += 8
        for gas in self.ai.gas_buildings:  # type: Unit
            if gas.is_ready:
                count += gas.ideal_harvesters
            else:
                count += 3
        return count

    async def gate_count_calc(self) -> int:
        current_gates = self.cache.own([UnitTypeId.GATEWAY, UnitTypeId.WARPGATE])
        current_gate_count = current_gates.amount

        # stalker resource usage with warpgates = (125 + 50) / 23 = 7.6086956521739130434782608695652
        # immortal resource usage = (275 + 100) / 39 =  9.6153846153846153846153846153846
        # stargate resource usage with voidrays = 250 + 150 / 43 = 9.3023255813953488372093023255814
        # nexus resource usage with probes = 50 / 12 = 4.1666666666666666666666666666667
        income = self.mineral_gather_rate + self.vespene_gather_rate
        output = current_gate_count * 7.61
        robos = self.cache.own(UnitTypeId.ROBOTICSFACILITY).amount

        stargates = self.cache.own(UnitTypeId.STARGATE).amount

        output += robos * 9.6
        output += stargates * 9.3

        if self.ai.supply_workers < self.desired_workers:
            output += self.cache.own(UnitTypeId.NEXUS).amount * 4.17

        gates_for_leftover = max(0, (self.knowledge.available_mineral + self.knowledge.available_gas) / 500)

        gates_in_use = 0

        for gate in current_gates:  # type: Unit
            if gate.type_id == UnitTypeId.GATEWAY:
                if gate.orders:
                    gates_in_use += 1
            else:
                if not self.knowledge.cooldown_manager.is_ready(gate.tag, AbilityId.WARPGATETRAIN_ZEALOT):
                    gates_in_use += 1

        if income > 40:
            addition = 2
        else:
            addition = 1
        gates = ceil((income - output) / 7.61 + gates_for_leftover) + current_gate_count
        gates = min(gates_in_use + addition, gates, 15, floor(self.mineral_gather_rate / 4))
        return gates
