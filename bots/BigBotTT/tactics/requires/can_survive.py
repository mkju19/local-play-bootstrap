from sharpy.knowledges import KnowledgeBot
from sharpy.plans.require import RequireCustom


class CanSurvive(RequireCustom):
    def __init__(self):
        super().__init__(CanSurvive.can_survive)

    @staticmethod
    def can_survive(ai: KnowledgeBot) -> bool:
        for zone in ai.zone_manager.expansion_zones:
            if zone.is_ours and zone.is_under_attack and zone.power_balance < -4:
                return False

        return ai.game_analyzer.army_can_survive


class CanSurviveSafe(RequireCustom):
    def __init__(self):
        super().__init__(CanSurvive.can_survive)

    @staticmethod
    def can_survive(ai: KnowledgeBot) -> bool:
        for zone in ai.zone_manager.expansion_zones:
            if zone.is_ours and zone.is_under_attack and zone.power_balance < 4:
                return False

        return ai.game_analyzer.army_at_least_small_advantage
