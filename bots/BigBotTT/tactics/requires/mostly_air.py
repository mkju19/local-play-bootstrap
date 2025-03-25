from sharpy.knowledges import Knowledge
from sharpy.managers.extensions.game_states import AirArmy
from sharpy.plans.require import RequireCustom


class MostlyAir(RequireCustom):
    def __init__(self):
        super().__init__(MostlyAir.mostly_air)

    @staticmethod
    def mostly_air(knowledge: Knowledge) -> bool:
        if knowledge.game_analyzer.enemy_power.air_presence < 5:
            # Don't have a real army, could be just a sole warp prism
            return False
        return knowledge.game_analyzer.enemy_air in {AirArmy.AllAir, AirArmy.AlmostAllAir}
