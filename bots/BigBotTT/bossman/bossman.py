import math
from typing import Union

import numpy as np
from scipy.special import expit

from bossman.backend import BackendType, Backend, BackendFactory
from bossman.utl import (
    fix_p,
    floor,
    insert_decision_context,
    populate_missing_decision_context_keys,
    read_decision_context,
)


class BossMan:
    def __init__(
            self,
            rounding_precision: int = 4,
            autosave=True,
            legacy=False,
            explore_constant=1.4,
            random_distribution=True,
            backend: Union[BackendType, Backend] = BackendType.JSON,
    ):
        self.match_decision_history: dict = {"decisions": []}
        self.rounding_precision = rounding_precision
        self.autosave = autosave
        self.legacy = legacy
        self.explore_constant = explore_constant
        self.random_distribution = random_distribution
        self.backend = BackendFactory.construct(backend)
        self.decision_stats = self.backend.load_decision_stats()

    def decide(self, decision_type, options, **context) -> (str, float):
        """
        Makes a decision between choices, taking into account match history.

        TODO: allow for decision scopes where the caller can register things like their opponent/race/etc in the decision
        TODO: have decisions with a similar (but not the same) set of scopes influence other decisions.
        """
        if "choices" in context:  # we reserve this keyword
            raise "You cannot use 'choices' as part of your context - it is a reserved keyword."

        context = dict(sorted(context.items()))  # keep a consistent key order

        # Retrieve percentage win for each option from
        chosen_count: list = []
        won_count: list = []

        if decision_type in self.decision_stats:
            populate_missing_decision_context_keys(
                self.decision_stats[decision_type], context
            )
            tmp_decision_context = read_decision_context(
                self.decision_stats[decision_type], context
            )

            if "choices" not in tmp_decision_context:
                tmp_decision_context["choices"] = {}

            decision_context = tmp_decision_context["choices"]

            # Intialize missing values
            for option in options:
                if option not in decision_context:
                    decision_context[option] = {"chosen_count": 0, "won_count": 0}

            # Prepare data for call to probabilities calc
            for key, decision in decision_context.items():
                # # omit missing historical options
                if key in options:
                    won_count.append(decision["won_count"])
                    chosen_count.append(decision["chosen_count"])

        else:
            # Intialize missing values
            self.decision_stats[decision_type] = {}

            option_stats = {}
            for option in options:
                option_stats[option] = {"chosen_count": 0, "won_count": 0}
                won_count.append(0)
                chosen_count.append(0)

            insert_decision_context(
                self.decision_stats[decision_type], context, option_stats
            )

        p = self._calc_choice_probabilities(np.array(chosen_count), np.array(won_count))

        if self.random_distribution:
            choice = np.random.choice(options, p=fix_p(p))
        else:
            choice = options[np.argmax(p)]

        decision_context = read_decision_context(
            self.decision_stats[decision_type], context
        )
        decision_context["choices"][choice]["chosen_count"] += 1
        self._record_match_decision(decision_type, context, options, choice)
        return choice, p[options.index(choice)]

    def _record_match_decision(self, decision_type, context, options, choice):
        self.match_decision_history["decisions"].append(
            {
                "type": decision_type,
                "context": context,
                "options": options,
                "choice": choice,
            }
        )

    def report_result(
            self,
            win: bool,
            save_to_file: bool = None,
            purge_match_decision_history: bool = True,
    ):
        """
        Registers the outcome of the current match.
        """
        if win:
            self.match_decision_history["outcome"] = 1

            for decision in self.match_decision_history["decisions"]:
                decision_context = read_decision_context(
                    self.decision_stats[decision["type"]], decision["context"]
                )
                decision_context["choices"][decision["choice"]]["won_count"] += 1

        if save_to_file is not None:  # override autosave behaviour
            if save_to_file:
                self.backend.save(self.decision_stats, self.match_decision_history)
            # else don't save (do nothing)
        elif self.autosave:
            self.backend.save(self.decision_stats, self.match_decision_history)

        if purge_match_decision_history:
            self.match_decision_history = {"decisions": []}

    def _calc_choice_probabilities(
            self, chosen_count: np.array, won_count: np.array
    ) -> np.array:
        """
        Determines the weighted probabilities for each choice.
        """
        win_perc = self._calc_win_perc(chosen_count, won_count)

        total_games = chosen_count.sum()
        # Apply that weight to each choice's win percentage
        weighted_probabilities = self._calc_weighted_probability(
            win_perc, chosen_count, total_games
        )

        # Scale probabilities back down so they sum to 1.0 again.
        prob_sum = np.sum(weighted_probabilities)
        scaled_probs = weighted_probabilities / prob_sum

        # Avoid rounding errors by taking the rounding error difference
        # scaled_probs = scaled_probs / scaled_probs.sum(axis=0, keepdims=1)
        scaled_probs = self._round_probabilities_sum(scaled_probs)

        # Sanity check in case of bug
        # prob_check_sum = np.sum(scaled_probs)
        # assert prob_check_sum == 1.0, f'Is there a bug? prob_check_sum was {prob_check_sum}'

        # print(f'Samples: {samples}')
        # print(f'Wins: {wins}')
        # print(f'Win %: {win_perc}')
        # print(f'probability_weight: {probability_weight}')
        # print(f'Prob Inv: {probability_weight}')
        # print(f'Actual Prob: {weighted_probabilities}')
        # print(f'Prob Sum: {prob_sum}')
        # print(f'chosen_count: {chosen_count}')
        # print(f'won_count Prob: {won_count}')
        # print(f'Scaled Prob: {scaled_probs}')
        # print(f'Prob Check Sum: {prob_check_sum}')

        return scaled_probs

    def _calc_win_perc(self, chosen_count, won_count):
        return np.divide(
            won_count,
            chosen_count,
            out=np.zeros_like(won_count, dtype=float),
            where=won_count != 0,
        )

    def _calc_weighted_probability(self, win_perc, chosen_count, total_games):
        if self.legacy:
            """
            mod: The higher this value, the quicker the weight fall off as chosen_count climbs
            """
            mod = 1.0
            # calculate a weight that will make low sample size choices more likely
            probability_weight = 1 - (expit(chosen_count * mod) - 0.5) * 2

            # Apply that weight to each choice's win percentage
            return win_perc + probability_weight
        else:
            return self._calc_ucb(win_perc, chosen_count, total_games)

    # Based on https://www.chessprogramming.org/UCT
    # Upper confidence bound:
    # UCB1 = win percentage + C * sqrt(ln(total_games) / visits)
    def _calc_ucb(self, win_perc, chosen_count, total_games):
        if total_games > 0:
            return win_perc + self.explore_constant * np.sqrt(
                math.log(total_games + 1) / chosen_count,
                out=np.ones_like(chosen_count, dtype=float) * 1e100,
                where=chosen_count != 0,
            )
        return np.ones_like(chosen_count, dtype=float)

    def _round_probabilities_sum(self, probabilities: np.array) -> np.array:
        probabilities = floor(probabilities, self.rounding_precision)
        round_amount = 1.0 - np.sum(probabilities)
        probabilities[0] += round_amount  # chuck it on the first one
        return probabilities

    def _extract_decision_keys(
            self, decision_type: str, analytics: dict, decision_data, context: list = None
    ):

        if context is None:
            context = []

        if "choices" in decision_data:
            scope_name = "_".join([decision_type] + context)
            analytics[scope_name] = {}
            analytics[scope_name]["times_considered"] = 0
            analytics[scope_name]["choices"] = {}
            for choice_name, choice in decision_data["choices"].items():
                analytics[scope_name]["times_considered"] += choice["chosen_count"]

                analytics[scope_name]["choices"][choice_name] = {}
                analytics[scope_name]["choices"][choice_name]["win_perc"] = np.asscalar(
                    self._calc_win_perc(choice["chosen_count"], choice["won_count"])
                )
                analytics[scope_name]["choices"][choice_name]["chosen_count"] = choice[
                    "chosen_count"
                ]
                analytics[scope_name]["choices"][choice_name]["won_count"] = choice[
                    "won_count"
                ]

            del decision_data["choices"]

        for context_id, context_id_value in decision_data.items():
            for context_value, context_value_data in context_id_value.items():
                new_context = list(context)
                new_context.append(context_value)
                self._extract_decision_keys(
                    decision_type, analytics, context_value_data, list(new_context)
                )

    def calc_analytics(self) -> dict:
        analytics = {}

        for decision_type in self.decision_stats.keys():
            self._extract_decision_keys(
                decision_type, analytics, self.decision_stats[decision_type]
            )

        # sort
        analytics = dict(
            reversed(
                sorted(analytics.items(), key=lambda item: item[1]["times_considered"])
            )
        )
        for decision_type, values in analytics.items():
            values["choices"] = dict(
                reversed(
                    sorted(
                        values["choices"].items(),
                        key=lambda item: (
                            item[1]["win_perc"],
                            -item[1]["chosen_count"],
                        ),
                    )
                )
            )

        return analytics

    def print_analytics(self):
        analytics = self.calc_analytics()
        for scope_name, values in analytics.items():
            print(f'{scope_name} - {values["times_considered"]} times considered')

            for choice in values["choices"]:
                print(
                    f"{choice:<30} "
                    f"Win %: {values['choices'][choice]['win_perc']:.2f} "
                    f"Chosen: {values['choices'][choice]['chosen_count']:>3} "
                    f"Won: {values['choices'][choice]['won_count']:>3}"
                )
