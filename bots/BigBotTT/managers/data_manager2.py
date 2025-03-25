from random import randint
from typing import List, Optional, Tuple, Dict, Union

from managers.extended_build_detector import ExtendedEnemyRushBuild, EnemyMacroBuild
from sharpy.managers.extensions import DataManager

BASE_WIN_VALUE: float = 1
WIN_DECAY: float = 0.1
MEANINGFUL_GAMES: int = int(round((BASE_WIN_VALUE - WIN_DECAY) / WIN_DECAY))


def data_str(dict_score: Dict[str, float], dict_games: Dict[str, int], dict_wins: Dict[str, int]) -> str:
    text: str = ""
    for key in dict_wins.keys():
        if text != "":
            text += ", "

        value_text = "{0:.2f}".format(dict_score.get(key))
        wins_text = str(dict_wins.get(key))
        text += f"{key}: {value_text}/{wins_text}/{dict_games.get(key, 0)}"
    return text


class BuildDataManager(DataManager):
    def select_opener(self, keys: List[str]) -> str:
        count = len(keys)
        ubound = len(keys) - 1
        results = self.data.results

        if len(results) == 0 or (self.ai.run_custom and self.ai.player_id != 1):
            build = keys[randint(0, ubound)]
            self.print(f"Target unknown | BO: {build}")
            return build
        else:
            last_build_result: Optional[Tuple[str, int]] = None
            dict_scores: Dict[str, float] = dict()
            dict_wins: Dict[str, int] = dict()
            dict_games: Dict[str, int] = dict()

            for result in results[::-1]:
                try:
                    response_type = result.build_used
                except:
                    continue  # Ignore old keys that are no longer used

                if response_type not in keys:
                    continue  # Ignore old keys that are no longer used
                else:
                    dict_games[response_type] = dict_games.get(response_type, 0) + 1
                    if result.result > 0:
                        win_score = 1
                    else:
                        win_score = 0

                    if last_build_result is None:
                        last_build_result = (response_type, result.result)

                    dict_wins[response_type] = dict_wins.get(response_type, 0) + win_score

                    multiplier = max(0.0, BASE_WIN_VALUE - dict_games[response_type] * WIN_DECAY)
                    dict_scores[response_type] = dict_scores.get(response_type, 0) + result.result * multiplier

        # Fill no data with values equivalent to victories
        for type in dict_games.keys():
            games = dict_games.get(type)

            if games < MEANINGFUL_GAMES:
                max_value = MEANINGFUL_GAMES * (MEANINGFUL_GAMES + 1) / 2 * WIN_DECAY * BASE_WIN_VALUE
                left_value = max_value - (games - (games + 1) * games / 2 * WIN_DECAY * BASE_WIN_VALUE)
                dict_scores[type] = dict_scores[type] + left_value

        best = []
        best_value = 0

        data_debug = data_str(dict_scores, dict_games, dict_wins)
        self.announce(f"The magic values are: {data_debug}")

        if len(dict_games) < count:
            # not all builds have been played yet
            not_used_keys = []
            for key in keys:
                if key not in dict_games:
                    not_used_keys.append(key)

            build = not_used_keys[randint(0, len(not_used_keys) - 1)]
            # Pick randomly not used key here
            self.announce(f"Looking for more magic: {build}")
            return build

        for key, val in dict_scores.items():
            if val > best_value:
                best = [key]
                best_value = val
            elif val == best_value:
                best.append(key)

        adjusted_keys = keys.copy()

        if len(best) == 0:
            if len(adjusted_keys) > 1 and last_build_result is not None and last_build_result[0] in adjusted_keys:
                if last_build_result[1] > 0:
                    adjusted_keys = [last_build_result[0]]
                elif last_build_result[1] < 0:
                    adjusted_keys.remove(last_build_result[0])

            ubound = len(adjusted_keys) - 1
            build = adjusted_keys[randint(0, ubound)]
            self.announce(f"Looking bleak, random selection: {build}")
            return build

        build = best[randint(0, len(best) - 1)]
        self.announce(f"Selected by value: {build}")
        return build

    @property
    def last_enemy_build(self) -> Tuple[Union[int, ExtendedEnemyRushBuild], Union[int, EnemyMacroBuild]]:
        if (
            not self.last_result
            or not hasattr(self.last_result, "enemy_macro_build")
            or not hasattr(self.last_result, "enemy_build")
        ):
            return ExtendedEnemyRushBuild.Macro, EnemyMacroBuild.StandardMacro

        return self.last_result.enemy_build, self.last_result.enemy_macro_build

    def announce(self, text: str):
        # self.knowledge.chat_manager.store_debug_build_values(text)
        self.print(text, False)
