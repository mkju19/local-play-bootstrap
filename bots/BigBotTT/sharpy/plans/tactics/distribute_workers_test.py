import math
import sys
from random import randint
from typing import Optional, Union, List

import pytest
from unittest import mock

from sc2.bot_ai import BotAI
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.constants import ALL_GAS, mineral_ids, IS_STRUCTURE, IS_MINE
from sc2.game_data import AbilityData
from sc2.position import Point2
from sc2.unit import Unit

from .distribute_workers import DistributeWorkers
from sharpy.general.zone import Zone
from sharpy.knowledges import Knowledge, SkeletonBot
from sharpy.managers.core import (
    UnitCacheManager,
    UnitRoleManager,
    ZoneManager,
    PathingManager,
    LostUnitsManager,
    PreviousUnitsManager,
)
from sharpy.managers.core.roles import UnitTask
from sharpy.managers.core.unit_value import BUILDING_IDS, UnitValue

MAIN_POINT = Point2((10, 10))
NATURAL_POINT = Point2((10, 60))
ENEMY_MAIN_POINT = Point2((90, 90))
ENEMY_NATURAL_POINT = Point2((90, 40))


async def fake(self):
    return None


class MockBot(SkeletonBot):
    def __init__(self):
        self.distance_calculation_method = 0
        self.unit_command_uses_self_do = False

    def configure_managers(self) -> Optional[List["ManagerBase"]]:
        return []


def mock_ai() -> BotAI:
    ai = MockBot()
    ai._initialize_variables()
    # ai = mock.Mock(bot_object)
    ai._distances_override_functions(0)
    ai.actions = []
    ai.config = {"general": mock.Mock(), "debug_log": mock.Mock()}
    ai.config["general"].getboolean = lambda x: False
    ai.config["debug_log"].getboolean = lambda x, fallback: False
    ai.my_race = Race.Protoss
    ai.enemy_race = Race.Protoss
    # run custom and player_id disables mocking
    ai.run_custom = True
    ai.player_id = 2
    ai.state = mock.Mock()
    ai.state.effects = []
    ai.state.visibility.__getitem__ = lambda s, x: 2

    ai.client = mock.Mock()
    ai.game_info = mock.Mock()
    ai.game_info.player_start_location = MAIN_POINT
    ai.game_info.start_locations = [ENEMY_MAIN_POINT]
    ai.game_info.placement_grid.height = 100
    ai.game_info.placement_grid.width = 100
    ai.game_info.map_center = Point2((50, 50))
    ai.game_info.map_name = "Mock"
    ai.game_info.terrain_height.__getitem__ = lambda s, x: 0
    ai.game_info.terrain_height.data_numpy = [0]
    ai.game_info.map_ramps = []

    ai.game_data = mock.Mock()
    ai.game_data.unit_types = {}
    ai.game_data.abilities = dict()
    ability_proto_mock = mock.Mock()
    ability_proto_mock.target = 4
    ability_proto_mock.ability_id = AbilityId.HARVEST_GATHER.value
    ability_proto_mock.remaps_to_ability_id = False
    ability_mock = AbilityData(ai.game_data, ability_proto_mock)
    ai.game_data.abilities[AbilityId.HARVEST_GATHER.value] = ability_mock
    ai.game_data.units = {
        UnitTypeId.MINERALFIELD.value: mock.Mock(),
        UnitTypeId.PROBE.value: mock.Mock(),
    }

    ai.game_data.units[UnitTypeId.MINERALFIELD.value].has_minerals = True
    ai.game_data.units[UnitTypeId.MINERALFIELD.value].attributes = {}
    ai.game_data.units[UnitTypeId.PROBE.value].attributes = {}

    for typedata in BUILDING_IDS:
        ai.game_data.units[typedata.value] = mock.Mock()
        ai.game_data.units[typedata.value].attributes = {IS_STRUCTURE}
        ai.game_data.units[typedata.value].has_minerals = False

    ai.game_data.units[UnitTypeId.ASSIMILATOR.value].has_vespene = True
    ai.game_data.units[UnitTypeId.ASSIMILATOR.value].has_minerals = False
    ai.game_data.units[UnitTypeId.ASSIMILATORRICH.value].has_vespene = True

    mineral = create_mineral(ai, Point2((16, 10)))
    mineral2 = create_mineral(ai, Point2((16, 60)))

    ai._expansion_positions_list = [MAIN_POINT, NATURAL_POINT, ENEMY_MAIN_POINT, ENEMY_NATURAL_POINT]
    ai._resource_location_to_expansion_position_dict = {mineral.position: MAIN_POINT, mineral2.position: NATURAL_POINT}

    return ai


async def mock_knowledge(ai) -> Knowledge:
    knowledge = Knowledge()
    ai.knowledge = knowledge
    knowledge.action_handler = mock.Mock()
    knowledge.version_manager = mock.Mock()
    # pf = mock.Mock()
    knowledge.pathing_manager = PathingManager()
    knowledge.pathing_manager.map = mock.Mock()
    knowledge.action_handler.start = fake
    knowledge.version_manager.start = fake
    knowledge.pathing_manager.start = fake
    knowledge.pathing_manager.path_finder_terrain = mock.Mock()
    knowledge.pathing_manager.map.get_zone = lambda param: 1 if param.distance_to(ai.start_location) < 12 else 2

    knowledge.pathing_manager.path_finder_terrain.find_path = lambda p1, p2: (
        [p1, p2],
        math.hypot(p1[0] - p2[0], p1[1] - p2[1]),
    )
    managers = [
        UnitCacheManager(),
        UnitValue(),
        UnitRoleManager(),
        PreviousUnitsManager(),
        LostUnitsManager(),
        knowledge.pathing_manager,
        ZoneManager(),
    ]

    knowledge.pre_start(ai, managers)

    knowledge.get_boolean_setting = lambda x: False
    knowledge.ai.state.game_loop = 1
    knowledge.ai.orders = []

    await knowledge.start()
    knowledge.zone_manager._expansion_zones = [
        Zone(MAIN_POINT, True, knowledge, knowledge.zone_manager),
        Zone(NATURAL_POINT, False, knowledge, knowledge.zone_manager),
    ]
    knowledge.iteration = 1

    knowledge._all_own = ai.all_own_units

    # await knowledge.roles.start(knowledge)
    # await knowledge.unit_cache.start(knowledge)
    await knowledge.unit_cache.update()

    await knowledge.zone_manager.start(knowledge)
    await knowledge.zone_manager.update()
    return knowledge


def create_mineral(ai: BotAI, position: Point2) -> Unit:
    mineral = mock_unit(ai, UnitTypeId.MINERALFIELD, position)
    ai.mineral_field.append(mineral)
    ai.resources.append(mineral)
    return mineral


def mock_unit(ai, type_id: UnitTypeId, position: Point2, progress: float = 1) -> Unit:
    proto_mock = mock.Mock()
    proto_mock.tag = randint(0, sys.maxsize)
    proto_mock.unit_type = type_id.value
    proto_mock.pos.x = position.x
    proto_mock.pos.y = position.y
    proto_mock.orders = []
    proto_mock.buff_ids = []

    if type_id in mineral_ids:
        proto_mock.mineral_contents = 1000
    else:
        proto_mock.mineral_contents = 0

    if type_id in ALL_GAS:
        proto_mock.vespene_contents = 1000
        proto_mock.assigned_harvesters = 0
        proto_mock.ideal_harvesters = 3
    else:
        proto_mock.vespene_contents = 0
    unit = Unit(proto_mock, ai)

    if type_id in {UnitTypeId.NEXUS}:
        proto_mock.assigned_harvesters = 0
        proto_mock.ideal_harvesters = 16
        ai.townhalls.append(unit)

    if type_id in ALL_GAS:
        ai.gas_buildings.append(unit)
        unit._type_data.has_minerals

    if unit.is_structure:
        proto_mock.health = 400  # Whatever
        proto_mock.health_max = 400  # Whatever
        proto_mock.shield = 400
        proto_mock.shield_max = 400
        ai.structures.append(unit)
        proto_mock.build_progress = progress
        ai.all_own_units.append(unit)
        proto_mock.alliance = IS_MINE

    if type_id in {UnitTypeId.PROBE}:
        proto_mock.health = 20
        proto_mock.health_max = 20
        proto_mock.shield = 20
        proto_mock.shield_max = 20
        ai.units.append(unit)
        ai.workers.append(unit)
        ai.all_own_units.append(unit)
        proto_mock.alliance = IS_MINE

    ai.all_units.append(unit)

    return unit


def set_fake_order(unit: Unit, command: AbilityId, target: Optional[Union[int, Point2]]):
    fake = mock.Mock()
    fake.ability_id = command.value
    if isinstance(target, int):
        fake.target_unit_tag = target
        fake.HasField = lambda key: False
    else:
        fake.target_world_space_pos = target
        fake.HasField = lambda key: True

    fake.progress = 0

    unit._proto.orders = [fake]


class TestDistributeWorkers:
    @pytest.mark.asyncio
    async def test_assign_idle_to_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))

        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(0, worker1)
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[0].tag

    @pytest.mark.asyncio
    async def test_assign_idle_to_gas(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 0
        nexus1._proto.ideal_harvesters = 0

        gas = mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        ai.units.append(worker1)
        ai.workers.append(worker1)
        ai.all_units.append(worker1)

        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(0, worker1)
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == gas.tag

    @pytest.mark.asyncio
    async def test_balance_assign_idle_to_gas(self):
        distribute_workers = DistributeWorkers(min_gas=1)
        distribute_workers.aggressive_gas_fill = True
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 0
        nexus1._proto.ideal_harvesters = 16

        gas = mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        ai.units.append(worker1)
        ai.workers.append(worker1)
        ai.all_units.append(worker1)

        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(0, worker1)
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == gas.tag

    @pytest.mark.asyncio
    async def test_balance_assign_idle_to_nexus(self):
        distribute_workers = DistributeWorkers(min_gas=0)
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 0
        nexus1._proto.ideal_harvesters = 16

        mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        ai.units.append(worker1)
        ai.workers.append(worker1)
        ai.all_units.append(worker1)

        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(0, worker1)
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[0].tag

    @pytest.mark.asyncio
    async def test_balance_max_gas_assign_idle_to_nexus(self):
        distribute_workers = DistributeWorkers(min_gas=0, max_gas=0)
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 16
        nexus1._proto.ideal_harvesters = 16

        mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        ai.units.append(worker1)
        ai.workers.append(worker1)
        ai.all_units.append(worker1)

        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(0, worker1)
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[0].tag

    @pytest.mark.asyncio
    async def test_evacuate_zone_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 1

        mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT))

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 60)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[1].tag)

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)
        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        knowledge.zone_manager.expansion_zones[0].needs_evacuation = True
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) == 1
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[1].tag

    @pytest.mark.asyncio
    async def test_force_evacuate_zone_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 1

        mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT))

        worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
        set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)
        knowledge = await mock_knowledge(ai)
        knowledge.roles.set_task(UnitTask.Gathering, worker1)
        knowledge.zone_manager.expansion_zones[0].needs_evacuation = True
        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[1].tag

    @pytest.mark.asyncio
    async def test_assign_surplus_to_gas(self):
        distribute_workers = DistributeWorkers(aggressive_gas_fill=True)
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 17

        gas = mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()

        assert len(ai.actions) == 1
        assert ai.actions[0].target.tag == gas.tag

    @pytest.mark.asyncio
    async def test_assign_surplus_to_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 17

        nexus2 = mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT))
        nexus2._proto.assigned_harvesters = 14

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        for i in range(0, 14):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 60)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[1].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].target.tag == ai.mineral_field[1].tag

    @pytest.mark.asyncio
    async def test_not_assign_surplus_to_not_ready_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 17

        nexus2 = mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT), 0.89)
        nexus2._proto.assigned_harvesters = 0

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) == 0

    @pytest.mark.asyncio
    async def test_assign_surplus_to_not_ready_nexus(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 17

        nexus2 = mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT), 0.91)
        nexus2._proto.assigned_harvesters = 0

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) > 0
        assert ai.actions[0].target.tag == ai.mineral_field[1].tag

    @pytest.mark.asyncio
    async def test_force_assign_to_gas(self):
        distribute_workers = DistributeWorkers(aggressive_gas_fill=True)
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 14

        gas = mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        for i in range(0, 14):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()

        assert len(ai.actions) == 1
        assert ai.actions[0].target.tag == gas.tag

    @pytest.mark.asyncio
    async def test_force_remove_from_gas(self):
        distribute_workers = DistributeWorkers(aggressive_gas_fill=True)
        distribute_workers.max_gas = 0
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 14

        gas = mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))
        gas._proto.assigned_harvesters = 1

        for i in range(0, 14):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        for i in range(0, 1):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, gas.tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()

        assert len(ai.actions) == 1
        assert ai.actions[0].unit.tag == worker1.tag
        assert ai.actions[0].target.tag == ai.mineral_field[0].tag

    @pytest.mark.asyncio
    async def test_no_force_assign_to_gas(self):
        distribute_workers = DistributeWorkers(aggressive_gas_fill=False)
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 14

        mock_unit(ai, UnitTypeId.ASSIMILATOR, Point2(MAIN_POINT))

        for i in range(0, 14):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()

        assert len(ai.actions) == 0

    @pytest.mark.asyncio
    async def test_do_not_send_excess_workers(self):
        distribute_workers = DistributeWorkers()
        ai = mock_ai()

        nexus1 = mock_unit(ai, UnitTypeId.NEXUS, Point2(MAIN_POINT))
        nexus1._proto.assigned_harvesters = 17

        nexus2 = mock_unit(ai, UnitTypeId.NEXUS, Point2(NATURAL_POINT))
        nexus2._proto.assigned_harvesters = 16

        for i in range(0, 17):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 10)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[0].tag)

        for i in range(0, 16):
            worker1 = mock_unit(ai, UnitTypeId.PROBE, Point2((20, 60)))
            set_fake_order(worker1, AbilityId.HARVEST_GATHER, ai.mineral_field[1].tag)

        knowledge = await mock_knowledge(ai)

        for worker in ai.workers:
            knowledge.roles.set_task(UnitTask.Gathering, worker)

        await distribute_workers.start(knowledge)
        await distribute_workers.execute()
        assert len(ai.actions) == 0
