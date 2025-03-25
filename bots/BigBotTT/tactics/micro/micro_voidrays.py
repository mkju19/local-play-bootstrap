from sc2.unit import Unit
from sharpy.combat.protoss import MicroVoidrays


class MicroVoidrays2(MicroVoidrays):
    def should_shoot(self, unit: Unit):
        return self.ready_to_shoot(unit)
