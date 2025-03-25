from ladder import run_ladder_game
from dummy.dummy1 import LadderBot
from sc2.player import Bot

dummy_bot = LadderBot()
race = dummy_bot.my_race
terran_bot = Bot(race, dummy_bot)


def main():
    # Ladder game started by LadderManager
    print("Starting ladder game...")
    result, opponentid = run_ladder_game(terran_bot)
    print(result, " against opponent ", opponentid)


if __name__ == "__main__":
    main()
