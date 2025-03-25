"""
---------------------------
BOT CLICADINHA
---------------------------

Made of with Ares Random Example Bot

https://github.com/AresSC2/ares-random-example


Using the Queens framework

https://github.com/raspersc2/queens-sc2

"""


from itertools import cycle
from typing import Optional

import numpy as np
from ares import AresBot
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    AMove,
    KeepUnitSafe,
    PathUnitToTarget,
    ShootTargetInRange,
    StutterUnitBack,
    UseAbility,
    AttackTarget,
)
from ares.behaviors.macro import AutoSupply, Mining, SpawnController, GasBuildingController, BuildWorkers, ExpansionController
from ares.consts import ALL_STRUCTURES, WORKER_TYPES, UnitRole, UnitTreeQueryType, BuildingPurpose
from cython_extensions import cy_closest_to, cy_in_attack_range, cy_pick_enemy_target
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
import time

from queens_sc2.queens import Queens



#_______________________________________________________________________________________________________________________
#          ARMY COMPOSITION
#_______________________________________________________________________________________________________________________

# this will be used for ares SpawnController behavior

# against Terran
ARMY_COMP_HYDRALING: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.ZERGLING: {"proportion": 0.8, "priority": 0},
        UnitID.HYDRALISK: {"proportion": 0.2, "priority": 1},
    }
}

# against Protoss
ARMY_COMP_LING: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.ZERGLING: {"proportion": 1.0, "priority": 0},
    }
}

# against other races
ARMY_COMP_ROACH: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.ROACH: {"proportion": 1.0, "priority": 0},
    }
}

# against other races
ARMY_COMP_LINGROACH: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.ZERGLING: {"proportion": 0.6, "priority": 0},
        UnitID.ROACH: {"proportion": 0.4, "priority": 0},

    }
}

# against terran
ARMY_COMP_MUTAROACH: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.MUTALISK: {"proportion": 0.9, "priority": 0},
        UnitID.ROACH: {"proportion": 0.1, "priority": 1 },

    }
}


# against flying units
ARMY_COMP_MUTAlLISK: dict[Race, dict] = {
    Race.Zerg: {
        UnitID.MUTALISK: {"proportion": 1.0, "priority": 0},

    }
}







COMMON_UNIT_IGNORE_TYPES: set[UnitID] = {
    UnitID.EGG,
    UnitID.LARVA,
    UnitID.CREEPTUMORBURROWED,
    UnitID.CREEPTUMORQUEEN,
    UnitID.CREEPTUMOR,
}


class MyBot(AresBot):
    expansions_generator: cycle
    current_base_target: Point2
    _begin_attack_at_supply: float
    BURROW_AT_HEALTH_PERC: float = 0.3
    UNBURROW_AT_HEALTH_PERC: float = 0.9
    last_debug_time = 0
    
    # instance of the queens class
    queens: Queens

    def __init__(self, game_step_override: Optional[int] = None):
        

        """Initiate custom bot

        Parameters
        ----------
        game_step_override :
            If provided, set the game_step to this value regardless of how it was
            specified elsewhere
        """
        super().__init__(game_step_override)
        self.tag_worker_build_2nd_base = 0
        self.tag_worker_build_3rd_base = 0
        self.tag_worker_build_roach_warren = 0
        self.tag_worker_build_hydra_den = 0
        self.tag_worker_build_spine_crawler = 0
        self.tag_worker_build_2nd_spine_crawler = 0
        self.tag_worker_build_3rd_spine_crawler = 0
        self.tag_worker_second_gas = 0
        self.overlord_retreated = False
        self.spineCrawlerCheeseDetected = False
        self.reaperFound = False
        self.bansheeFound = False
        self.tag_worker_build_first_spore = 0
        self.tag_worker_build_second_spore = 0
        self.random_race_discovered = False
        self.one_proxy_barracks_found = False
        self.two_proxy_barracks_found = False
        self.mutalisksFound = False
        self.proxy_pylon_found = False        
        self.one_proxy_gateWay_found = False
        self.two_proxy_gateWay_found = False
        self.photon_cannon_found = False
        self.terran_flying_structures = False
        self.tag_worker_build_spire = 0
        self.is_roach_attacking = False
        self.defending = False
        self.liberatorFound = False
        self.SapwnControllerOn = True
        self.speedMiningOn = True
        self.enemy_has_3_bases = False
        self.scout_targets = {}  # Dicionário para armazenar os alvos dos scouts
        self.enemies_on_creep = {}  # Dicionário para armazenar as unidades inimigas que estão no creep
        self.enemy_went_worker_rush = False
        self.bo_changed = False
        self.my_overlords = {}


        self._commenced_attack: bool = False


        self.creep_queen_tags: Set[int] = set()
        self.max_creep_queens: int = 1




        self.creep_queen_policy: Dict = {
            "creep_queens": {
                "active": True,
                "priority": 0,
                "max": self.max_creep_queens,
                "defend_against_air": True,
                "defend_against_ground": True,
            },
            "inject_queens": {""
                "active": True,
                "priority": 1,
            },
            "defence_queens": {"active": False},
        }
        

    @property
    def attack_target(self) -> Point2:
        if self.enemy_structures:
            # using a faster cython alternative here, see docs for all available functions
            # https://aressc2.github.io/ares-sc2/api_reference/cython_extensions/index.html
            return cy_closest_to(self.start_location, self.enemy_structures).position
        # not seen anything in early game, just head to enemy spawn
        elif self.time < 240.0:
            return self.enemy_start_locations[0]
        # else search the map
        else:
            # cycle through expansion locations
            if self.is_visible(self.current_base_target):
                self.current_base_target = next(self.expansions_generator)

            return self.current_base_target
        
#_______________________________________________________________________________________________________________________
#          ON START
#_______________________________________________________________________________________________________________________

    async def on_start(self) -> None:
        await super(MyBot, self).on_start()
    
        self.EnemyRace = self.enemy_race  
        self.rally_point_set = False
        self.first_base = self.townhalls.first
        self.second_base = None
        self.first_overlord = self.units(UnitID.OVERLORD).first
        self.worker_scout_tag = 0
        self.enemy_strategy = []

    
        self.current_base_target = self.enemy_start_locations[0]
        self.expansions_generator = cycle(
            [pos for pos in self.expansion_locations_list]
        )
    
        # Find the ID of the opponent    
        self.opponent = self.opponent_id
        if self.opponent_id is not None:
            await self.chat_send(self.opponent_id)
            print("The opponent ID is: ")
            print(self.opponent_id)
        else:
            print("Warning: opponent_id is None, cannot send chat message.")
    
        # BotKiller
        if self.opponent_id == "da0fe671-3f51-4c48-8ac2-252cb67ee545":
            self._begin_attack_at_supply = 1
    
        # Apidae
        elif self.opponent_id == "c033a97a-667d-42e3-91e8-13528ac191ed":
            self._begin_attack_at_supply = 1
    
        # LiShiMinV2
        elif self.opponent_id == "0d0d9c44-2520-457d-84ba-7f6ffe167a3e":
            self._begin_attack_at_supply = 1
    
        else:
            if self.EnemyRace == Race.Terran:
                self._begin_attack_at_supply = 40
    
            elif self.EnemyRace == Race.Protoss:
                self._begin_attack_at_supply = 10
    
            elif self.EnemyRace == Race.Zerg:
                self._begin_attack_at_supply = 30
    
            elif self.EnemyRace == Race.Random:
                self._begin_attack_at_supply = 10
    
        # Initialize the queens class
        self.queens = Queens(
            self, queen_policy=self.creep_queen_policy
        )
    
        # Send Overlord to scout on the second base
        await self.send_overlord_to_scout()

#_______________________________________________________________________________________________________________________
#          SEND OVERLORD TO SCOUT
#_______________________________________________________________________________________________________________________


    async def send_overlord_to_scout(self):
        # Select the first Overlord
        overlord = self.units(UnitID.OVERLORD).first
    
        enemy_natural_location = self.mediator.get_enemy_nat
    
        # Get the enemy's start location
        #enemy_natural_location = self.mediator.get_enemy_nat
        #target = self.mediator.get_closest_overlord_spot(from_pos=enemy_natural_location)
        target = enemy_natural_location.position.towards(self.game_info.map_center, 13)
        # Send the Overlord to the new position
        self.do(overlord.move(target))
        hg_spot = self.mediator.get_closest_overlord_spot(
            from_pos=enemy_natural_location
        )
        overlord.move(hg_spot, queue=True)


#_______________________________________________________________________________________________________________________
#          ON STEP
#_______________________________________________________________________________________________________________________

    async def on_step(self, iteration: int) -> None:
        await super(MyBot, self).on_step(iteration)

        #await self.debug_tool()


        self._macro()


        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_from_role
        # see `self.on_unit_created` where we originally assigned units ATTACKING role
        forces: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)

        if self._commenced_attack:
            self._micro(forces)

        elif self.get_total_supply(forces) >= self._begin_attack_at_supply:
            self._commenced_attack = True

        if self._commenced_attack == True:
            # If we don't have enough army, stop attacking and build more units

            #RETURN TO BASE
            if self.get_total_supply(forces) < self._begin_attack_at_supply:
                self._commenced_attack = False
                self.is_roach_attacking = False
                # If the army is not atacking and is far form the base, move it to the base
                for unit in forces:
                    bases = self.structures(UnitID.HATCHERY).ready
                    if bases.amount >= 2:
                        # In the file where distance_math_hypot is called, ensure the arguments are not None
                        if unit.position_tuple is not None and self.mediator.get_own_nat.towards(self.game_info.map_center, 6) is not None:
                            if unit.distance_to(self.mediator.get_own_nat) > 30:
                                if not unit.is_attacking:
                                    unit.move(self.mediator.get_own_nat.towards(self.game_info.map_center, 6))
                        else:
                            # Handle the case where one of the positions is None, e.g., log a warning or take alternative action
                            print("Warning: One of the positions is None")
                    else:
                        unit.move(self.first_base.position.towards(self.game_info.map_center, 3))

        

        if self.EnemyRace == Race.Terran:
            await self.build_queens()
            await self.is_terran_agressive()
            await self.is_bunker_rush()
            await self.search_proxy_barracks()
            await self.burrow_roaches()
            await self.findReaper()
            await self.attack_reaper()
            await self.attack_banshee()
            await self.defend()
            await self.build_range_upgrades()
            await self.build_armor_upgrades()
            await self.is_structures_flying()
            await self.build_lair()
            #await self.build_spine_crawlers()
            await self.make_zerglings()
            await self.find_liberator()
            await self.turnOffSpawningControllerOnEarlyGame()
            await self.is_3_base_terran()
            await self.is_worker_rush()
            #await self.build_hydra_den()



            if "Bunker_Rush" in self.enemy_strategy:
                await self.build_roach_warren()
                await self.research_burrow()
            #if "2_Base_Terran" in self.enemy_strategy:


            if "Proxy_Barracks" in self.enemy_strategy:
                #await self.cancel_second_base()
                await self.retreat_overlords()
                await self.harass_worker_proxy_barracks()
                await self.build_spine_crawlers()
                await self.change_to_bo_DefensiveVsProxyBarracks()


            if "Banshee" in self.enemy_strategy:
                await self.make_spores()

            if "Liberator" in self.enemy_strategy:
                await self.make_spores()


            if "Flying_Structures" in self.enemy_strategy:
                #await self.build_lair()
                #await self.build_hydra_den()
                #self.register_behavior(BuildWorkers(to_count=80))
                await self.build_spire()
                #await self.build_second_gas()
                await self.build_four_gas()
                await self.mutalisk_attack()
                await self.spread_overlords()


            #if "3_Base_Terran" in self.enemy_strategy:
                #await self.macro_protocol()

        if self.EnemyRace == Race.Protoss:
            await self.build_queens()
            await self.is_protoss_agressive()
            await self.build_mellee_upgrades()
            await self.build_armor_upgrades()
            await self.burrow_roaches()
            await self.defend()
            await self.search_proxy_vs_protoss()
            await self.is_worker_rush()

            if "Protoss_Agressive" in self.enemy_strategy:
                await self.build_spine_crawlers()

            if "Protoss_Agressive" not in self.enemy_strategy:
                await self.build_next_base()

            if "2_Proxy_Gateway" in self.enemy_strategy:
                await self.cancel_second_base()
                await self.retreat_overlords()
                await self.make_spines_on_main()
                await self.build_roach_warren()
                await self.research_burrow()

            #if "Cannon_Rush" in self.enemy_strategy:
                #await self.cancel_second_base()
                #await self.build_roach_warren()
                #await self.research_burrow()
                #await self.build_second_gas()

            if "Cannon_Rush" not in self.enemy_strategy:
                await self.build_next_base()


        if self.EnemyRace == Race.Zerg:
            await self.find_cheese_spine_crawler()
            await self.burrow_roaches()
            await self.find_mutalisks()
            await self.is_worker_rush()

            if "Mutalisk" in self.enemy_strategy:
                await self.make_spores()
        
            if "Cheese_Spine_Crawler" in self.enemy_strategy:
                await self.turnOffSpeedMining()
                await self.worker_defense()
                await self.turnOnSpeedMiningAtTimeX(95)


        if self.EnemyRace == Race.Random:
            await self.build_queens()
            await self.discover_race()
            await self.build_spine_crawlers()
            await self.burrow_roaches()
            await self.defend()
            await self.is_worker_rush()


#_______________________________________________________________________________________________________________________
#          QUEENS
#_______________________________________________________________________________________________________________________

        queens: Units = self.units(UnitID.QUEEN)
        # work out if more creep queen_control are required
        if queens and len(self.creep_queen_tags) < self.max_creep_queens:
            queens_needed: int = self.max_creep_queens - len(self.creep_queen_tags)
            new_creep_queens: Units = queens.take(queens_needed)
            for queen in new_creep_queens:
                self.creep_queen_tags.add(queen.tag)




        # separate the queen units selection
        creep_queens: Units = queens.tags_in(self.creep_queen_tags)
        other_queens: Units = queens.tags_not_in(self.creep_queen_tags)
        # call the queen library to handle our creep queen_control
        await self.queens.manage_queens(iteration, creep_queens)

        # we have full control of the other queen_control
        #for queen in other_queens:
            #if queen.distance_to(self.game_info.map_center) > 12:
                #queen.attack(self.game_info.map_center)




    async def build_queens(self):
        for th in self.townhalls.ready:
            # Check if the number of queens is less than the number of townhalls
            if len(self.units(UnitID.QUEEN)) <= len(self.townhalls.ready):
                # Check if we're not already training a queen
                if not self.already_pending(UnitID.QUEEN):
                    # If we're not, train a queen
                    self.do(th.train(UnitID.QUEEN))


    async def build_next_base(self):
        if self.minerals > 300:
            target = await self.get_next_expansion()
            if self.tag_worker_build_2nd_base == 0:
                if worker := self.mediator.select_worker(target_position=target):                
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                    self.tag_worker_build_2nd_base = worker
                    #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                    self.mediator.build_with_specific_worker(worker=self.tag_worker_build_2nd_base, structure_type=UnitID.HATCHERY, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)


    async def build_next_next_base(self):
        if len(self.townhalls.ready) == 2:
            target = await self.get_next_expansion()
            if self.tag_worker_build_3rd_base == 0:
                if worker := self.mediator.select_worker(target_position=target):                
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                    self.tag_worker_build_3rd_base = worker
                    #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                    self.mediator.build_with_specific_worker(worker=self.tag_worker_build_3rd_base, structure_type=UnitID.HATCHERY, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)



    async def build_mellee_upgrades(self):
        if self.structures(UnitID.EVOLUTIONCHAMBER).ready:
            if self.structures(UnitID.SPAWNINGPOOL).ready:
                if not self.already_pending_upgrade(UpgradeId.ZERGLINGATTACKSPEED):
                    if self.can_afford(UpgradeId.ZERGLINGATTACKSPEED):
                        self.research(UpgradeId.ZERGLINGATTACKSPEED)
                if not self.already_pending_upgrade(UpgradeId.ZERGMELEEWEAPONSLEVEL1):
                    if self.can_afford(UpgradeId.ZERGMELEEWEAPONSLEVEL1):
                        self.research(UpgradeId.ZERGMELEEWEAPONSLEVEL1)
                if not self.already_pending_upgrade(UpgradeId.ZERGMELEEWEAPONSLEVEL2):
                    if self.can_afford(UpgradeId.ZERGMELEEWEAPONSLEVEL2):
                        self.research(UpgradeId.ZERGMELEEWEAPONSLEVEL2)
                if not self.already_pending_upgrade(UpgradeId.ZERGMELEEWEAPONSLEVEL3):
                    if self.can_afford(UpgradeId.ZERGMELEEWEAPONSLEVEL3):
                        self.research(UpgradeId.ZERGMELEEWEAPONSLEVEL3)

    async def build_armor_upgrades(self):
        if self.structures(UnitID.EVOLUTIONCHAMBER).ready:
            if self.structures(UnitID.SPAWNINGPOOL).ready:
                if not self.already_pending_upgrade(UpgradeId.ZERGGROUNDARMORSLEVEL1):
                    if self.can_afford(UpgradeId.ZERGGROUNDARMORSLEVEL1):
                        self.research(UpgradeId.ZERGGROUNDARMORSLEVEL1)
                if not self.already_pending_upgrade(UpgradeId.ZERGGROUNDARMORSLEVEL2):
                    if self.can_afford(UpgradeId.ZERGGROUNDARMORSLEVEL2):
                        self.research(UpgradeId.ZERGGROUNDARMORSLEVEL2)
                if not self.already_pending_upgrade(UpgradeId.ZERGGROUNDARMORSLEVEL3):
                    if self.can_afford(UpgradeId.ZERGGROUNDARMORSLEVEL3):
                        self.research(UpgradeId.ZERGGROUNDARMORSLEVEL3)


    async def build_range_upgrades(self):
        if self.structures(UnitID.EVOLUTIONCHAMBER).ready:
            if self.structures(UnitID.SPAWNINGPOOL).ready:
                if not self.already_pending_upgrade(UpgradeId.ZERGMISSILEWEAPONSLEVEL1):
                    if self.can_afford(UpgradeId.ZERGMISSILEWEAPONSLEVEL1):
                        self.research(UpgradeId.ZERGMISSILEWEAPONSLEVEL1)
                if not self.already_pending_upgrade(UpgradeId.ZERGMISSILEWEAPONSLEVEL2):
                    if self.can_afford(UpgradeId.ZERGMISSILEWEAPONSLEVEL2):
                        self.research(UpgradeId.ZERGMISSILEWEAPONSLEVEL2)
                if not self.already_pending_upgrade(UpgradeId.ZERGMISSILEWEAPONSLEVEL3):
                    if self.can_afford(UpgradeId.ZERGMISSILEWEAPONSLEVEL3):
                        self.research(UpgradeId.ZERGMISSILEWEAPONSLEVEL3)



    async def build_lair(self):
        if not self.structures(UnitID.LAIR):
            if self.can_afford(UnitID.LAIR):
                th: Unit = self.first_base
                th(AbilityId.UPGRADETOLAIR_LAIR)

    async def build_hydra_den(self):
        if self.structures(UnitID.LAIR).ready:
            if self.structures(UnitID.HYDRALISKDEN).amount == 0 and not self.already_pending(UnitID.HYDRALISKDEN):
                if self.tag_worker_build_hydra_den == 0:
                    if self.can_afford(UnitID.HYDRALISKDEN):
                        positions = self.mediator.get_behind_mineral_positions(th_pos=self.first_base.position)
                        reference = positions[1] if positions else None
                        target = reference.towards(self.first_base, -1)


                        #await self.build(UnitID.HYDRALISKDEN, near=target)
                        if worker := self.mediator.select_worker(target_position=target):                
                            self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                            self.tag_worker_build_hydra_den = worker
                            #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                            self.mediator.build_with_specific_worker(worker=self.tag_worker_build_hydra_den, structure_type=UnitID.HYDRALISKDEN, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)

    async def discover_race(self):
        if self.random_race_discovered == False:
            if self.time < 60:
                for unit in self.enemy_structures:
                    if unit.name == 'Nexus':
                        await self.chat_send("Tag: Random_Protoss")
                        self.enemy_strategy.append("Random_Protoss")
                        self.random_race_discovered = True
                        break
                    elif unit.name == 'CommandCenter':
                        await self.chat_send("Tag: Random_Terran")
                        self.enemy_strategy.append("Random_Terran")
                        self.random_race_discovered = True
                        break
                    elif unit.name == 'Hatchery':
                        await self.chat_send("Tag: Random_Zerg")
                        self.enemy_strategy.append("Random_Zerg")
                        self.random_race_discovered = True
                        break

    async def build_spine_crawlers(self):
        if self.rally_point_set == True:
            if self.structures(UnitID.SPINECRAWLER).amount == 0 and not self.already_pending(UnitID.SPINECRAWLER):
                if self.tag_worker_build_spine_crawler == 0:
                    if self.can_afford(UnitID.SPINECRAWLER):
                        my_base_location = self.mediator.get_own_nat
                        # Send the second Overlord in front of second base to scout
                        target = my_base_location.position.towards(self.game_info.map_center, 6)                   
                        #await self.build(UnitID.HYDRALISKDEN, near=target)
                        if worker := self.mediator.select_worker(target_position=target):                
                            self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                            self.tag_worker_build_spine_crawler = worker
                            #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                            self.mediator.build_with_specific_worker(worker=self.tag_worker_build_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)
                            print("first Spine Crawler")

            if self.tag_worker_build_2nd_spine_crawler == 0:
                print("Second Spine Crawler")
                if self.can_afford(UnitID.SPINECRAWLER):
                    my_base_location = self.mediator.get_own_nat
                    # Send the second Overlord in front of second base to scout
                    reference = my_base_location.position.towards(self.game_info.map_center, 6)
                    first_base_location = self.first_base                    
                    target = reference.towards(first_base_location.position, 2)                      
                    #await self.build(UnitID.HYDRALISKDEN, near=target)
                    if worker := self.mediator.select_worker(target_position=target):                
                        self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                        self.tag_worker_build_2nd_spine_crawler = worker
                        #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                        self.mediator.build_with_specific_worker(worker=self.tag_worker_build_2nd_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)
                        print("Second Spine Crawler")
            if self.tag_worker_build_3rd_spine_crawler == 0:
                
                if self.can_afford(UnitID.SPINECRAWLER):
                    my_base_location = self.mediator.get_own_nat
                    # Send the second Overlord in front of second base to scout
                    reference = my_base_location.position.towards(self.game_info.map_center, 6)
                    first_base_location = self.first_base                    
                    target = reference.towards(first_base_location.position, - 2)             
                    #await self.build(UnitID.HYDRALISKDEN, near=target)
                    if worker := self.mediator.select_worker(target_position=target):                
                        self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                        self.tag_worker_build_3rd_spine_crawler = worker
                        #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                        self.mediator.build_with_specific_worker(worker=self.tag_worker_build_3rd_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)
                        print("third Spine Crawler")


    async def is_terran_agressive(self):
        # Verify if the terran opponent has only one base. If so, it is an aggressive terran and build a spine crawler
        if self.time == 140:
            found_command_center = False
            for unit in self.enemy_structures:
                if unit.name == 'CommandCenter':
                    found_command_center = True
                    break  # Break the loop if find the Command Center
            
            if not found_command_center:
                if "Terran_Agressive" not in self.enemy_strategy:
                    await self.chat_send("Tag: Terran_Agressive")
                    self.enemy_strategy.append("Terran_Agressive")
                    #await self.build_spine_crawlers()
            else:
                if "2_Base_Terran" not in self.enemy_strategy:
                    await self.chat_send("Tag: 2_Base_Terran")
                    self.enemy_strategy.append("2_Base_Terran")

    async def is_protoss_agressive(self):
        if not self.enemy_strategy:
        #verify if the protoss opponent has only one base. If so, it is an agressive terran and build a spine crawler
            if self.time > 142 and self.time < 143:
                found_nexus = False
                for unit in self.enemy_structures:
                    if unit.name == 'Nexus':
                        found_nexus = True
                        break  # Breake the loop if find the Nexus
                if not found_nexus:
                    await self.chat_send("Tag: Protoss_Agressive")
                    self.enemy_strategy.append("Protoss_Agressive")
                else:
                    await self.chat_send("Tag: 2_Base_Protoss")
                    self.enemy_strategy.append("2_Base_Protoss")



    async def is_bunker_rush(self):
        if not self.enemy_strategy:
        #verify if the protoss opponent has only one base. If so, it is an agressive terran and build a spine crawler
            if self.time > 114 and self.time < 115:
                found_bunker = False
                for unit in self.enemy_structures:
                    if unit.name == 'Bunker':
                        found_bunker = True
                        break  # Breake the loop if find the Nexus
                if found_bunker:
                    await self.chat_send("Tag: Bunker_Rush")
                    self.enemy_strategy.append("Bunker_Rush")


    async def build_roach_warren(self):
        if self.structures(UnitID.SPAWNINGPOOL).ready:
            if self.structures(UnitID.ROACHWARREN).amount == 0 and not self.already_pending(UnitID.ROACHWARREN):
                if self.tag_worker_build_roach_warren == 0:
                    if self.can_afford(UnitID.ROACHWARREN):
                        map_center = self.game_info.map_center
                        position_towards_map_center = self.start_location.towards(map_center, distance=5)
                        target = await self.find_placement(UnitID.ROACHWARREN, near=position_towards_map_center, placement_step=1)
                        #await self.build(UnitID.HYDRALISKDEN, near=target)
                        if worker := self.mediator.select_worker(target_position=target):                
                            self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                            self.tag_worker_build_roach_warren = worker
                            #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                            self.mediator.build_with_specific_worker(worker=self.tag_worker_build_roach_warren, structure_type=UnitID.ROACHWARREN, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)

    async def research_burrow(self):
        if self.structures(UnitID.ROACHWARREN).ready:
            if not self.already_pending_upgrade(UpgradeId.BURROW):
                if self.can_afford(UpgradeId.BURROW):
                    self.research(UpgradeId.BURROW)


    async def search_proxy_barracks(self):
        if self.time < 94:
            if self.one_proxy_barracks_found == False:
                for unit in self.enemy_structures:
                    if unit.name == 'Barracks':
                        self.one_proxy_barracks_found = True
                        await self.chat_send("Tag: Proxy_Barracks")
                        self.enemy_strategy.append("Proxy_Barracks")
                        break

            if self.two_proxy_barracks_found == False:
                barracks_count = sum(1 for structure in self.enemy_structures if structure.name == "Barracks")
                if barracks_count > 1:
                    await self.chat_send("Tag: 2 Proxy_Barracks")
                    self.enemy_strategy.append("2_Proxy_Barracks")
                    self.two_proxy_barracks_found = True


    async def build_second_gas(self):
        if self.structures(UnitID.HATCHERY).amount == 2:
            self.register_behavior(GasBuildingController(to_count = 2))


    async def build_four_gas(self):
        if self.structures(UnitID.HATCHERY).amount >= 2:
            self.register_behavior(GasBuildingController(to_count = 4))
            
            


    async def cancel_second_base(self):
        hatcheries = self.structures(UnitID.HATCHERY)
        if hatcheries:
            for hatchery in hatcheries:
                if not hatchery.is_ready:
                    self.mediator.cancel_structure(structure=hatchery)


    async def retreat_overlords(self):
        #retreat the overlords to the first base so they don't die
        if self.overlord_retreated == False:
            for overlord in self.units(UnitID.OVERLORD):
                if overlord.distance_to(self.first_base.position) < 30:  # Defina a distância que considera "perto"
                    overlord.move(self.first_base.position)
                    self.overlord_retreated = True


    async def worker_defense(self):
        spine_crawler_amount = 0
        for spinecrawler in self.enemy_structures(UnitID.SPINECRAWLER):
            if spinecrawler.distance_to(self.first_base) < 20:
                spine_crawler_amount = spine_crawler_amount+1
                for drone in self.workers:
                    self.mediator.switch_roles(from_role=UnitRole.GATHERING, to_role=UnitRole.DEFENDING)
                    drone.attack(spinecrawler.position)


        #if spine_crawler_amount == 0 and self.spineCrawlerCheeseDetected:
            #self.spineCrawlerCheeseDetected = False
            #for drone in self.workers:
                #self.mediator.assign_role(tag = drone.tag, role = UnitRole.GATHERING)
                #self.speedMiningOn = True
                


    async def find_cheese_spine_crawler(self):
        if self.time < 180:
            if self.spineCrawlerCheeseDetected == False:
                for spinecrawler in self.enemy_structures(UnitID.SPINECRAWLER):
                    if spinecrawler.distance_to(self.first_base) < 20:
                        self.spineCrawlerCheeseDetected = True
                        await self.chat_send("Tag: Cheese Spine Crawler")
                        self.enemy_strategy.append("Cheese_Spine_Crawler")


    async def burrow_roaches(self):
        # Burrow the roaches when they are low health
        for roach in self.units(UnitID.ROACH):
            if roach.health_percentage <= self.BURROW_AT_HEALTH_PERC:
                roach(AbilityId.BURROWDOWN_ROACH)


        for burrowed_roach in self.units(UnitID.ROACHBURROWED):
            if burrowed_roach.health_percentage > self.UNBURROW_AT_HEALTH_PERC:
                burrowed_roach(AbilityId.BURROWUP_ROACH)


    async def findReaper(self):
        if self.reaperFound == False:
            for unit in self.enemy_units:
                if unit.name == 'Reaper':
                    self.reaperFound = True
                    break
            if self.reaperFound:
                await self.chat_send("Tag: Reaper")

    async def attack_reaper(self):
        if self.reaperFound:
            for unit in self.enemy_units:
                if unit.name == 'Reaper':
                    if self.has_creep(unit.position):
                        for queen in self.units(UnitID.QUEEN):
                            if queen.energy < 25:
                                queen.attack(unit.position)

    async def attack_banshee(self):
        if self.bansheeFound == False:
            for unit in self.enemy_units:
                if unit.name == 'Banshee':
                    self.bansheeFound = True
                    break
            if self.bansheeFound:
                await self.chat_send("Tag: Banshee")
                self.enemy_strategy.append("Banshee")

        if self.bansheeFound:
            for unit in self.enemy_units:
                if unit.name == 'Banshee':
                    if self.has_creep(unit.position):
                        for queen in self.units(UnitID.QUEEN):
                            if queen.energy < 25:
                                queen.attack(unit.position)


    async def make_spores(self):
        if self.tag_worker_build_first_spore == 0:
            if self.can_afford(UnitID.SPORECRAWLER):
                my_base_location = self.first_base
                # Send the second Overlord in front of second base to scout
                target = my_base_location.position.towards(self.game_info.map_center, -5)                   
                if worker := self.mediator.select_worker(target_position=target):                
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                    self.tag_worker_build_first_spore = worker
                    #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                    self.mediator.build_with_specific_worker(worker=self.tag_worker_build_first_spore, structure_type=UnitID.SPORECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)

        if self.tag_worker_build_second_spore == 0:
            if self.second_base is not None:
                if self.can_afford(UnitID.SPORECRAWLER):
                    my_base_location = self.second_base
                    # Send the second Overlord in front of second base to scout
                    target = my_base_location.position.towards(self.game_info.map_center, -5)                   
                    if worker := self.mediator.select_worker(target_position=target):                
                        self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                        self.tag_worker_build_second_spore = worker
                        #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                        self.mediator.build_with_specific_worker(worker=self.tag_worker_build_second_spore, structure_type=UnitID.SPORECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)

    async def make_spines_on_main(self):
        if self.structures(UnitID.SPAWNINGPOOL).ready:
            if self.structures(UnitID.SPINECRAWLER).amount == 0 and not self.already_pending(UnitID.SPINECRAWLER):
                if self.tag_worker_build_spine_crawler == 0:
                    if self.can_afford(UnitID.SPINECRAWLER):
                        my_ramp = self.main_base_ramp.top_center
                        # Send the second Overlord in front of second base to scout
                        target = my_ramp.position.towards(self.first_base, 6)                   
                        if worker := self.mediator.select_worker(target_position=target):                
                            self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                            self.tag_worker_build_spine_crawler = worker
                            #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                            self.mediator.build_with_specific_worker(worker=self.tag_worker_build_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)

        if self.tag_worker_build_spine_crawler != 0:
            if self.can_afford(UnitID.SPINECRAWLER):
                my_ramp = self.main_base_ramp.top_center
                reference = my_ramp.position.towards(self.first_base, 6)
                target = reference.towards(self.game_info.map_center, 2)
                if worker := self.mediator.select_worker(target_position=target):                
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                    self.tag_worker_build_2nd_spine_crawler = worker
                    #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                    self.mediator.build_with_specific_worker(worker=self.tag_worker_build_2nd_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)


        if self.tag_worker_build_2nd_spine_crawler != 0:
            if self.can_afford(UnitID.SPINECRAWLER):
                my_ramp = self.main_base_ramp.top_center
                reference = my_ramp.position.towards(self.first_base, 6)
                target = reference.towards(self.game_info.map_center, -2)
                if worker := self.mediator.select_worker(target_position=target):                
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                    self.tag_worker_build_3rd_spine_crawler = worker
                    #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                    self.mediator.build_with_specific_worker(worker=self.tag_worker_build_3rd_spine_crawler, structure_type=UnitID.SPINECRAWLER, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)


    async def defend(self):
        enemy_on_creep = False
        for enemyUnit in self.enemy_units:
            if self.has_creep(enemyUnit.position):
                if not enemyUnit.is_flying:
                    enemy_on_creep = True
                    self.defending = True
                    self._commenced_attack = True
                    # Adicionar a unidade inimiga ao dicionário enemies_on_creep
                    self.enemies_on_creep[enemyUnit.tag] = enemyUnit
            else:
                # Remover a unidade inimiga do dicionário enemies_on_creep se ela sair da creep
                if enemyUnit.tag in self.enemies_on_creep:
                    del self.enemies_on_creep[enemyUnit.tag]
    
        # Remover unidades inimigas do dicionário se elas não estiverem mais na lista de unidades inimigas
        self.enemies_on_creep = {tag: unit for tag, unit in self.enemies_on_creep.items() if unit in self.enemy_units}
    
        if not enemy_on_creep:
            forces: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
            if self.get_total_supply(forces) < self._begin_attack_at_supply:
                self._commenced_attack = False
                self.defending = False
                for unit in forces:
                    if self.second_base is not None:         
                        unit.move(self.second_base.position.towards(self.game_info.map_center, 4))                        
                    else:
                        unit.move(self.first_base.position.towards(self.game_info.map_center, 6))
            else:
                self._commenced_attack = True


    async def find_mutalisks(self):
        if self.mutalisksFound == False:
            for unit in self.enemy_units:
                if unit.name == 'Mutalisk':
                    self.mutalisksFound = True
                    break
            if self.mutalisksFound:
                await self.chat_send("Tag: Mutalisk")
                self.enemy_strategy.append("Mutalisk")


    async def search_proxy_vs_protoss(self):
        if self.time < 94:
            if self.proxy_pylon_found == False:
                for unit in self.enemy_structures:
                    if unit.name == 'Pylon':
                        self.proxy_pylon_found = True
                        await self.chat_send("Tag: Proxy_Pylon")
                        self.enemy_strategy.append("Proxy_Pylon")
                        break

            if self.one_proxy_gateWay_found == False:
                for unit in self.enemy_structures:
                    if unit.name == 'Gateway':
                        self.one_proxy_gateWay_found = True
                        await self.chat_send("Tag: Proxy_Gateway")
                        self.enemy_strategy.append("Proxy_Gateway")
                        break

            if self.two_proxy_gateWay_found == False:
                gateWays_count = sum(1 for structure in self.enemy_structures if structure.name == "Gateway")
                if gateWays_count > 1:
                    await self.chat_send("Tag: 2_Proxy_Gateway")
                    self.enemy_strategy.append("2_Proxy_Gateway")
                    self.two_proxy_gateWay_found = True

            if self.photon_cannon_found == False:
                for unit in self.enemy_structures:
                    if unit.name == 'PhotonCannon':
                        expansion = self.mediator.get_own_nat
                        if unit.distance_to(expansion) < 20:
                            self.photon_cannon_found = True
                            await self.chat_send("Tag: Cannon_Rush")
                            self.enemy_strategy.append("Cannon_Rush")
                            break


    async def is_structures_flying(self):
        #Some terrans, lift their structures when they feel they are about to lose.
        #This function aims to recognize this situation to make mutaliskas
        if self.time > 240:
            if self.terran_flying_structures == False:
                for unit in self.enemy_structures:
                    if unit.is_flying:
                        if unit.distance_to(self.enemy_start_locations[0]) < 12:
                            await self.chat_send("Tag: Flying_Structures")
                            self.enemy_strategy.append("Flying_Structures")
                            self.terran_flying_structures = True


    async def build_spire(self):
        if self.structures(UnitID.SPIRE).ready.amount < 1:
            self.SapwnControllerOn = False

        else:
            self.SapwnControllerOn = True

        if self.structures(UnitID.LAIR).ready:
            if self.structures(UnitID.SPIRE).amount == 0 and not self.already_pending(UnitID.SPIRE):
                if self.tag_worker_build_spire == 0:
                    if self.can_afford(UnitID.SPIRE):
                        positions = self.mediator.get_behind_mineral_positions(th_pos=self.first_base.position)
                        target = positions[0] if positions else None
                        #await self.build(UnitID.HYDRALISKDEN, near=target)
                        if worker := self.mediator.select_worker(target_position=target):                
                            self.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)
                            self.tag_worker_build_spire = worker
                            #self.mediator.build_with_specific_worker(worker, UnitID.HATCHERY, target, BuildingPurpose.NORMAL_BUILDING)
                            self.mediator.build_with_specific_worker(worker=self.tag_worker_build_spire, structure_type=UnitID.SPIRE, pos=target, building_purpose=BuildingPurpose.NORMAL_BUILDING)



    async def make_zerglings(self):
        if "Flying_Structures" not in self.enemy_strategy:
            if self.minerals >700:
                if self.vespene < 25:
                    self.train(UnitID.ZERGLING)


    async def find_liberator(self):
        if self.liberatorFound == False:
            for unit in self.enemy_units:
                if unit.name == 'Liberator':
                    self.liberatorFound = True
                    break
            if self.liberatorFound:
                await self.chat_send("Tag: Liberator")
                self.enemy_strategy.append("Liberator")


    async def turnOffSpawningControllerOnEarlyGame(self):
        if self.build_order_runner.build_completed == False:
            self.SapwnControllerOn = False
        else:
            self.SapwnControllerOn = True

    async def turnOffSpeedMining(self):
        if self.speedMiningOn == True:
            self.speedMiningOn = False


    async def turnOnSpeedMiningAtTimeX(self, x: int):
        if self.time > x:
            self.spineCrawlerCheeseDetected = False
            for drone in self.workers:
                self.mediator.assign_role(tag = drone.tag, role = UnitRole.GATHERING)
            self.speedMiningOn = True


    async def harass_worker_proxy_barracks(self):
        worker_scouts: Units = self.mediator.get_units_from_role(
            role=UnitRole.BUILD_RUNNER_SCOUT, unit_type=self.worker_type
        )
        
        for scout in worker_scouts:
            self.mediator.switch_roles(
                from_role=UnitRole.BUILD_RUNNER_SCOUT, to_role=UnitRole.HARASSING)

        worker_scouts: Units = self.mediator.get_units_from_role(
            role=UnitRole.HARASSING, unit_type=self.worker_type
        )


        # Adicionar todos os SCVs encontrados na lista de scout_targets
        for unit in self.enemy_units:
            if unit.name == 'SCV' and unit.tag not in self.scout_targets:
                self.scout_targets[unit.tag] = unit
    
        # Remover SCVs que não estão mais na lista de unidades inimigas
        self.scout_targets = {tag: target for tag, target in self.scout_targets.items() if target in self.enemy_units}
    
        for scout in worker_scouts:
            # Se a lista de scout_targets não estiver vazia, atacar o primeiro SCV da lista
            if self.scout_targets:
                first_target_tag = next(iter(self.scout_targets))
                first_target = self.scout_targets[first_target_tag]
                scout.attack(first_target)
            else:
                # Se a lista de scout_targets estiver vazia, atacar a primeira estrutura inimiga
                if self.enemy_structures:
                    scout.attack(self.enemy_structures.first.position)


    async def is_3_base_terran(self):
        if self.time > 300:
            if self.enemy_has_3_bases == False:
                if self.mediator.get_enemy_has_base_outside_natural == True:
                    await self.chat_send("Tag: 3_Base_Terran")
                    self.enemy_strategy.append("3_Base_Terran")
                    self.enemy_has_3_bases = True



    async def macro_protocol(self):
        if self.workers.amount < 70:
            self.SapwnControllerOn = False
            self.register_behavior(ExpansionController(to_count=5, max_pending=2))
            self.register_behavior(BuildWorkers(to_count=70))           
            self.register_behavior(GasBuildingController(to_count=4, max_pending=2))

        else:
            self.SapwnControllerOn = True



    async def mutalisk_attack(self):
        mutalisks: Units = self.units(UnitID.MUTALISK)
        
        for mutalisk in mutalisks:
            # Encontrar unidades inimigas voadoras
            flying_enemies = [unit for unit in self.enemy_units if unit.is_flying]
            
            if flying_enemies:
                # Atacar a primeira unidade voadora encontrada
                target = flying_enemies[0]
                mutalisk.attack(target)
            else:
                # Se não houver unidades voadoras, atacar a primeira estrutura inimiga
                if self.enemy_structures:
                    target = self.enemy_structures.first
                    mutalisk.attack(target)



    async def spread_overlords(self):
        expansion_locations = list(self.expansion_locations_list)
        overlord_tags = list(self.my_overlords.keys())  # Obter as tags dos Overlords em ordem
    
        # Iterar sobre cada expansão e atribuir um Overlord
        for i, expansion in enumerate(expansion_locations):
            if i < len(overlord_tags):
                overlord_tag = overlord_tags[i]
                overlord = self.my_overlords[overlord_tag]
    
                # Enviar o Overlord para a expansão apenas se ele não estiver se movendo
                #if not overlord.is_moving:
                self.do(overlord.move(expansion))

    async def is_worker_rush(self):
        if self.enemy_went_worker_rush == False:
            if self.mediator.get_enemy_worker_rushed == True:
                await self.chat_send("Tag: Worker_Rush")
                self.enemy_strategy.append("Worker_Rush")
                self.enemy_went_worker_rush = True


    async def change_to_bo_DefensiveVsProxyBarracks(self):
        if self.bo_changed == False:
            self.build_order_runner.switch_opening("DefensiveVsProxyBarracks")
            self.bo_changed = True
#_______________________________________________________________________________________________________________________
#          DEBUG TOOL
#_______________________________________________________________________________________________________________________

    async def debug_tool(self):
        current_time = time.time()
        if current_time - self.last_debug_time >= 1:  # Se passou mais de um segundo
            #print(self.mediator.get_all_enemy)
            #print("Enemy Race: ", self.EnemyRace)
            #print("Second Base: ", self.second_base)
            print("Enemy Strategy: ", self.enemy_strategy)
            #print("Creep Queens: ", self.creep_queen_tags)
            #print("Creep Queen Policy: ", self.creep_queen_policy)
            #print("RallyPointSet: ", self.rally_point_set)
            print("Enemy Structures: ", self.enemy_structures)
            print("Enemy Units: ", self.enemy_units)
            #print("Behind mineral positions: ", self.mediator.get_behind_mineral_positions(th_pos=self.first_base.position))
            #print("Enemy Start Location: ", self.enemy_start_locations[0])
            #print("Build Completed: ", self.build_order_runner.build_completed)
            #print("Scout Targets", self.scout_targets)
            #print("Max creep queens:", self.max_creep_queens)
            #print("Creep queen tags:", self.creep_queen_tags)
            #print("Enemies on creep:", self.enemies_on_creep)
            #print("worker rush:", self.mediator.get_enemy_worker_rushed)
            print("My Overlords:", self.my_overlords)
            #print("FirstBase: ", self.first_base)
            #print("SecondBase: ", self.second_base)
            self.last_debug_time = current_time  # Atualizar a última vez que a ferramenta de debug foi chamada


#_______________________________________________________________________________________________________________________
#          ON UNIT TOOK DAMAGE
#_______________________________________________________________________________________________________________________

    # If the building is attacked and is not complete, cancel the construction

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await super(MyBot, self).on_unit_took_damage(unit, amount_damage_taken)


        # If the building is attacked and is not complete, cancel the construction
        compare_health: float = max(50.0, unit.health_max * 0.09)
        if unit.health < compare_health and unit.is_structure:
            unit(AbilityId.CANCEL_BUILDINPROGRESS)


        if unit.type_id == UnitID.ROACH:
            self.is_roach_attacking = True
             



#_______________________________________________________________________________________________________________________
#          ON UNIT CREATED
#_______________________________________________________________________________________________________________________


    async def on_unit_created(self, unit: Unit) -> None:
        """
        Can use burnysc2 hooks as usual, just add a call to the
        parent method before your own logic.
        """
        await super(MyBot, self).on_unit_created(unit)

        # Adicionar Overlords ao dicionário self.my_overlords
        if unit.type_id == UnitID.OVERLORD:
            self.my_overlords[unit.tag] = unit


        # assign our forces ATTACKING by default
        if unit.type_id not in WORKER_TYPES and unit.type_id not in {
            UnitID.QUEEN,
            UnitID.MULE,
            UnitID.OVERLORD,
            UnitID.MUTALISK,
        }:
            # here we are making a request to an ares manager via the mediator
            # See https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)



        # Send the second Overlord to scout on the second base
        if unit.type_id == UnitID.OVERLORD and self.units(UnitID.OVERLORD).amount == 2:
            my_base_location = self.mediator.get_own_nat

 
            # Send the second Overlord in front of second base to scout
            target = my_base_location.position.towards(self.game_info.map_center, 5)
        
            # Send the Overlord to the new position
            self.do(unit.move(target))
            await self.chat_send("Tag: Version_250324f")
            

        # Send the second Overlord to scout on the third base
        if unit.type_id == UnitID.OVERLORD and self.units(UnitID.OVERLORD).amount == 3:
            enemy_third = self.mediator.get_enemy_third

 
            # Send the second Overlord in front of second base to scout
            target = enemy_third.position.towards(self.game_info.map_center, 9)
        
            # Send the Overlord to the new position
            self.do(unit.move(target))


        # Send the second Overlord to scout on the fourth base
        if unit.type_id == UnitID.OVERLORD and self.units(UnitID.OVERLORD).amount == 4:
            enemy_fourth = self.mediator.get_enemy_fourth

 
            # Send the second Overlord in front of second base to scout
            target = enemy_fourth.position.towards(self.game_info.map_center, 9)
        
            # Send the Overlord to the new position
            self.do(unit.move(target))





        # For the third Overlord and beyond, send them behind the first base
        elif unit.type_id == UnitID.OVERLORD and self.units(UnitID.OVERLORD).amount >= 5:

            target = self.first_base.position.towards(self.game_info.map_center, -15)  # Get a position behind of the first base
            self.do(unit.move(target))

#_______________________________________________________________________________________________________________________
#          ON BUILDING CONSTRUCTION COMPLETE
#_______________________________________________________________________________________________________________________


    async def on_building_construction_complete(self, unit: Unit) -> None:
        await super(MyBot, self).on_building_construction_complete(unit)


        #when the second base is built, set the rally point to the second base
        if unit.type_id == UnitID.HATCHERY:
            self.rally_point_set = True  
            bases = self.structures(UnitID.HATCHERY).ready
            if bases.amount == 2:
                for base in bases:
                    if base.tag != self.first_base.tag:
                        self.second_base = base
                        break

            if self.second_base is not None:         
                rally_point = self.second_base.position.towards(self.game_info.map_center, 6)                          

                for hatcherys in self.structures(UnitID.HATCHERY).ready:
                    self.do(hatcherys(AbilityId.RALLY_HATCHERY_UNITS, rally_point))


#_______________________________________________________________________________________________________________________
#          DEF MACRO
#_______________________________________________________________________________________________________________________

    def _macro(self) -> None:
        # MINE
        # ares-sc2 Mining behavior
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/macro_behaviors.html#ares.behaviors.macro.mining.Mining
        
        if self.speedMiningOn == True:
            self.register_behavior(Mining())

        # MAKE SUPPLY
        # ares-sc2 AutoSupply
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/macro_behaviors.html#ares.behaviors.macro.auto_supply.AutoSupply
        if self.build_order_runner.build_completed:
            self.register_behavior(AutoSupply(base_location=self.start_location))




#_______________________________________________________________________________________________________________________
        # BUILD ARMY
        # ares-sc2 SpawnController
#_______________________________________________________________________________________________________________________


        if self.SapwnControllerOn == True:


            if self.EnemyRace == Race.Terran:
                if "Flying_Structures" in self.enemy_strategy:
                    self.register_behavior(SpawnController(ARMY_COMP_MUTAlLISK[self.race]))
                else:
                    self.register_behavior(SpawnController(ARMY_COMP_ROACH[self.race]))
            
            elif self.EnemyRace == Race.Protoss:
                if "2_Proxy_Gateway" in self.enemy_strategy:
                    self.register_behavior(SpawnController(ARMY_COMP_ROACH[self.race]))
                elif "Cannon_Rush" in self.enemy_strategy:
                    self.register_behavior(SpawnController(ARMY_COMP_ROACH[self.race]))
                else:
                    self.register_behavior(SpawnController(ARMY_COMP_LING[self.race]))
            
            elif self.EnemyRace == Race.Zerg:
                self.register_behavior(SpawnController(ARMY_COMP_ROACH[self.race]))
            
            elif self.EnemyRace == Race.Random:
                self.register_behavior(SpawnController(ARMY_COMP_ROACH[self.race]))

        # see also `ProductionController` for ongoing generic production, not needed here
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/macro_behaviors.html#ares.behaviors.macro.spawn_controller.ProductionController




        self._zerg_specific_macro()

#_______________________________________________________________________________________________________________________
#          DEF _MICRO
#_______________________________________________________________________________________________________________________

    def _micro(self, forces: Units) -> None:
        # make a fast batch distance query to enemy units for all our units
        # key: unit tag, value: units in range of that unit tag
        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_in_range
        # as zerg we will only interact with ground enemy, else we should get all enemy
        query_type: UnitTreeQueryType = (
            UnitTreeQueryType.EnemyGround
            if self.race == Race.Zerg
            else UnitTreeQueryType.AllEnemy
        )
        near_enemy: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=forces,
            distances=15,
            query_tree=query_type,
            return_as_dict=True,
        )

        # get a ground grid to path on, this already contains enemy influence
        grid: np.ndarray = self.mediator.get_ground_grid

        # make a single call to self.attack_target property
        # otherwise it keep calculating for every unit
        target: Point2 = self.attack_target

        # Atualizar o alvo se houver inimigos na creep
        if self.enemies_on_creep:
            first_enemy_on_creep = next(iter(self.enemies_on_creep.values()))
            target = first_enemy_on_creep.position


        # use `ares-sc2` combat maneuver system
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/combat_behaviors.html
        for unit in forces:
            """
            Set up a new CombatManeuver, idea here is to orchestrate your micro
            by stacking behaviors in order of priority. If a behavior executes
            then all other behaviors will be ignored for this step.
            """

            attacking_maneuver: CombatManeuver = CombatManeuver()
            # we already calculated close enemies, use unit tag to retrieve them
            all_close: Units = near_enemy[unit.tag].filter(
                lambda u: not u.is_memory and u.type_id not in COMMON_UNIT_IGNORE_TYPES
            )
            only_enemy_units: Units = all_close.filter(
                lambda u: u.type_id not in ALL_STRUCTURES
            )

            if unit.type_id in [UnitID.ROACH, UnitID.ROACHBURROWED]:
                # only roaches can burrow
                burrow_behavior: CombatManeuver = self.burrow_behavior(unit)
                attacking_maneuver.add(burrow_behavior)

            # enemy around, engagement control
            if all_close:
                # ares's cython version of `cy_in_attack_range` is approximately 4
                # times speedup vs burnysc2's `all_close.in_attack_range_of`

                # idea here is to attack anything in range if weapon is ready
                # check for enemy units first



#_______________________________________________________________________________________________________________________
#          ROACH
#_______________________________________________________________________________________________________________________

                if unit.type_id in [UnitID.ROACH]:
                    if in_attack_range := cy_in_attack_range(unit, only_enemy_units):
                        # `ShootTargetInRange` will check weapon is ready
                        # otherwise it will not execute
                        attacking_maneuver.add(
                            ShootTargetInRange(unit=unit, targets=in_attack_range)
                        )
                    # then enemy structures
                    elif in_attack_range := cy_in_attack_range(unit, all_close):
                        attacking_maneuver.add(
                            ShootTargetInRange(unit=unit, targets=in_attack_range)
                        )

                    enemy_target: Unit = cy_pick_enemy_target(all_close)

                    # low shield, keep protoss units safe
                    if self.race == Race.Protoss and unit.shield_percentage < 0.3:
                        attacking_maneuver.add(KeepUnitSafe(unit=unit, grid=grid))

                    else:
                        attacking_maneuver.add(
                            StutterUnitBack(unit=unit, target=enemy_target, grid=grid)
                        )

#_______________________________________________________________________________________________________________________
#          ZERGLING
#_______________________________________________________________________________________________________________________

                if unit.type_id in [UnitID.ZERGLING]:
                    if self.units(UnitID.ROACH).amount > 0:
                        if self.is_roach_attacking:
                            attacking_maneuver.add(AMove(unit=unit, target=target))
                        
                        else:
                            attacking_maneuver.add(KeepUnitSafe(unit=unit, grid=grid))
                
                    else:
                        attacking_maneuver.add(AMove(unit=unit, target=target))


#_______________________________________________________________________________________________________________________
#          ROACH BURROWED
#_______________________________________________________________________________________________________________________

                if unit.type_id in [UnitID.ROACHBURROWED]:
                    attacking_maneuver.add(KeepUnitSafe(unit=unit, grid=grid))





#_______________________________________________________________________________________________________________________
#          OTHER UNITS
#_______________________________________________________________________________________________________________________


                else:
                    attacking_maneuver.add(AMove(unit=unit, target=target))

                    
            # no enemy around, path to the attack target
            else:
                attacking_maneuver.add(
                    PathUnitToTarget(unit=unit, grid=grid, target=target)
                )
                attacking_maneuver.add(AMove(unit=unit, target=target))

            # DON'T FORGET TO REGISTER OUR COMBAT MANEUVER!!
            self.register_behavior(attacking_maneuver)

    def burrow_behavior(self, roach: Unit) -> CombatManeuver:
        """
        Burrow or unburrow roach
        """
        burrow_maneuver: CombatManeuver = CombatManeuver()
        if roach.is_burrowed and roach.health_percentage > self.UNBURROW_AT_HEALTH_PERC:
            burrow_maneuver.add(UseAbility(AbilityId.BURROWUP_ROACH, roach, None))
        elif (
            not roach.is_burrowed
            and roach.health_percentage <= self.BURROW_AT_HEALTH_PERC
        ):
            burrow_maneuver.add(UseAbility(AbilityId.BURROWDOWN_ROACH, roach, None))

        return burrow_maneuver



#_______________________________________________________________________________________________________________________
#          ZERG MACRO
#_______________________________________________________________________________________________________________________


    def _zerg_specific_macro(self) -> None:
        if self.EnemyRace == Race.Terran:  
            
            if (not self.already_pending_upgrade(UpgradeId.BURROW)):
                self.research(UpgradeId.BURROW)

            if (not self.already_pending_upgrade(UpgradeId.GLIALRECONSTITUTION)):
                self.research(UpgradeId.GLIALRECONSTITUTION)

            if (not self.already_pending_upgrade(UpgradeId.TUNNELINGCLAWS)):
                self.research(UpgradeId.TUNNELINGCLAWS)



        if self.EnemyRace == Race.Protoss:
            if (not self.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED)):
                self.research(UpgradeId.ZERGLINGMOVEMENTSPEED)       
        else:        
            if (
                not self.already_pending_upgrade(UpgradeId.BURROW)
                and self.townhalls.idle
                and self.build_order_runner.build_completed
                and self.can_afford(UpgradeId.BURROW)
            ):
                self.research(UpgradeId.BURROW)
    """
        for queen in self.mediator.get_own_army_dict[UnitID.QUEEN]:
            if queen.energy >= 25 and self.townhalls:
                queen(AbilityId.EFFECT_INJECTLARVA, self.townhalls[0])

    Can use `python-sc2` hooks as usual, but make a call the inherited method in the superclass
    Examples:

    # async def on_end(self, game_result: Result) -> None:
    #     await super(MyBot, self).on_end(game_result)
    #
    #     # custom on_end logic here ...
    #

    #     # custom on_building_construction_complete logic here ...
    #
    # async def on_unit_destroyed(self, unit_tag: int) -> None:
    #     await super(MyBot, self).on_unit_destroyed(unit_tag)
    #
    #     # custom on_unit_destroyed logic here ...
    #
    # async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
    #     await super(MyBot, self).on_unit_took_damage(unit, amount_damage_taken)
    #
    #     # custom on_unit_took_damage logic here ...


    async def build_zerglings(self):
        if (self.minerals/ self.vespene + 1) > 5 and self.minerals > 1000:
            for larva in self.units(UnitID.LARVA):
                # Check if we can afford a Zergling and have enough supply
                if self.can_afford(UnitID.ZERGLING) and self.supply_left > 0:
                    # If we can, train a Zergling
                    self.do(larva.train(UnitID.ZERGLING))
    """