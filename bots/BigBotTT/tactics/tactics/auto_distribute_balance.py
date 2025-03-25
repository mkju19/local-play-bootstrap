from sc2 import UnitTypeId
from sharpy.plans.tactics import DistributeWorkers


class AutoDistributeBalance(DistributeWorkers):
    async def execute(self) -> bool:
        self.adjust_gas_balance()
        return await super().execute()

    def adjust_gas_balance(self):
        if (
            self.ai.vespene < 50
            and self.ai.minerals > 200
            and self.ai.state.score.collection_rate_vespene == 0
            and self.cache.own(UnitTypeId.CYBERNETICSCORE).ready.amount > 0
        ):
            self.aggressive_gas_fill = True
            self.min_gas = 1
        elif self.ai.vespene < 100 and self.ai.minerals > 600:
            self.aggressive_gas_fill = True
            self.min_gas = 1
        elif len(self.ai.workers) < 12 and self.ai.vespene > 400 and self.ai.minerals < 50:
            self.max_gas = 0
        elif self.max_gas == 0 and self.ai.minerals > 200 and self.ai.vespene < 150:
            self.max_gas = None
