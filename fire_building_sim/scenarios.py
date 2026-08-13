"""Ready-made scenario builders and simulation launchers.

This module replaces notebook-style global state. It explicitly creates the
building, room catalogue, agents, and simulation in the correct order.
"""
from __future__ import annotations

from typing import Optional, Tuple

from fire_building_sim.config import DATA_DIR
from fire_building_sim.agents import create_default_agents
from fire_building_sim.building_factory import (
    create_sample_building,
    build_room_catalog_from_model,
    save_sample_building,
)
from fire_building_sim.fire_simulation import run_simulation
from fire_building_sim.simulation_runners import (
    run_fire_until_extinguished,
    run_sim_in_chunks,
    run_sim_in_chunks_until_extinguished,
    run_and_save_sim_in_chunks_until_extinguished,
)
from fire_building_sim.simulation_settings import (
    ALL_HISTORY_PARAMETERS,
    BASIC_HISTORY_PARAMETERS,
    DEFAULT_NR_TICKS,
    DEFAULT_START_FIRE_AT_COORD,
    DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    DEFAULT_SNAPSHOT_INTERVAL,
    DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PROBABILISTIC,
    DEFAULT_SAVE_FULL_HISTORY,
)


def build_sample_world():
    """Create the sample building, room catalogue, and default agents."""
    global_model = create_sample_building()
    room_catalogue = build_room_catalog_from_model(global_model)
    agents = create_default_agents(room_catalogue)
    return global_model, room_catalogue, agents


def run_custom_simulation(
    nr_ticks: int,
    start_fire_at_coord: Tuple[int, int, int],
    probabilistic: bool,
    save_full_history: bool,
    snapshot_interval: int,
    save_history_parameters,
    fire_dept_arrival_coords: Tuple[int, int, int],
    fire_dept_response_time: float,
    random_seed: Optional[int] = None,
):
    """Build and run the default sample fire simulation. Returns the sim object."""
    global_model, room_catalogue, agents = build_sample_world()
    sim = run_simulation(
        global_model=global_model,
        nr_ticks_to_simulate=nr_ticks,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=save_history_parameters,
        agents=agents,
        probabilistic=probabilistic,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        start_fire_at_coord=start_fire_at_coord,
        random_seed=random_seed,
    )
    return sim


def run_sample_simulation(
    nr_ticks: int = DEFAULT_NR_TICKS,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = True,
    save_full_history: bool = True,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    save_history_parameters = BASIC_HISTORY_PARAMETERS,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    random_seed: Optional[int] = None,
):
    """Build and run the default sample fire simulation. Returns the sim object."""
    global_model, room_catalogue, agents = build_sample_world()
    sim = run_simulation(
        global_model=global_model,
        nr_ticks_to_simulate=nr_ticks,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=save_history_parameters,
        agents=agents,
        probabilistic=probabilistic,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        start_fire_at_coord=start_fire_at_coord,
        random_seed=random_seed,
    )
    return sim


def save_default_data():
    """Save global_model.pkl and room_catalogue.pkl into the project data folder."""
    return save_sample_building(DATA_DIR)



def run_full_history_simulation(
    nr_ticks: int = DEFAULT_NR_TICKS,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = True,
    save_full_history: bool = True,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    random_seed: Optional[int] = None,
):
    """Run the sample simulation while saving every supported history field."""
    return run_sample_simulation(
        nr_ticks=nr_ticks,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=ALL_HISTORY_PARAMETERS,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        random_seed=random_seed,
    )

def run_sample_simulation_until_extinguished(
    max_ticks: int = DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = True,
    save_full_history: bool = True,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    save_history_parameters = BASIC_HISTORY_PARAMETERS,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    verbose: bool = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    random_seed: Optional[int] = None,
):
    """Build the sample simulation and run until fire is extinguished or max_ticks is reached.

    Returns the sim object. Two convenience attributes are added:
        sim.extinguished
        sim.until_extinguished_max_ticks
    """
    # nr_ticks=0 initializes the building, agents, fire department, initial fire,
    # and seed snapshot, but does not advance the simulation yet.
    sim = run_sample_simulation(
        nr_ticks=0,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=save_history_parameters,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        random_seed=random_seed,
    )

    extinguished = run_fire_until_extinguished(
        sim=sim,
        max_ticks=max_ticks,
        verbose=verbose,
    )

    sim.extinguished = extinguished
    sim.until_extinguished_max_ticks = max_ticks
    return sim


def run_full_history_simulation_until_extinguished(
    max_ticks: int = DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = True,
    save_full_history: bool = True,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    verbose: bool = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    random_seed: Optional[int] = None,
):
    """Run the sample simulation until extinguished while saving every supported history field."""
    return run_sample_simulation_until_extinguished(
        max_ticks=max_ticks,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=ALL_HISTORY_PARAMETERS,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        verbose=verbose,
        random_seed=random_seed,
    )

def run_full_history_simulation_fixed_ticks_chunked(
    nr_ticks: int = DEFAULT_NR_TICKS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = DEFAULT_PROBABILISTIC,
    save_full_history: bool = DEFAULT_SAVE_FULL_HISTORY,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    verbose: bool = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    random_seed: Optional[int] = None,
):
    """Run the full-history sample simulation for a fixed number of ticks in chunks."""
    sim = run_sample_simulation(
        nr_ticks=0,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=ALL_HISTORY_PARAMETERS,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        random_seed=random_seed,
    )

    completed, sim_time_after = run_sim_in_chunks(
        sim=sim,
        total_ticks=nr_ticks,
        chunk_size=chunk_size,
        verbose=verbose,
    )
    sim.chunked_completed = completed
    sim.chunk_size = chunk_size
    sim.requested_ticks = nr_ticks
    sim.sim_time_after_chunked_run = sim_time_after
    return sim


def run_full_history_simulation_until_extinguished_chunked(
    max_ticks: int = DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = DEFAULT_PROBABILISTIC,
    save_full_history: bool = DEFAULT_SAVE_FULL_HISTORY,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    verbose: bool = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    random_seed: Optional[int] = None,
):
    """Run full-history simulation in chunks until extinguished or max_ticks is reached."""
    sim = run_sample_simulation(
        nr_ticks=0,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=ALL_HISTORY_PARAMETERS,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        random_seed=random_seed,
    )

    extinguished, sim_time_after = run_sim_in_chunks_until_extinguished(
        sim=sim,
        chunk_size=chunk_size,
        max_total_ticks=max_ticks,
        verbose=verbose,
    )
    sim.extinguished = extinguished
    sim.until_extinguished_max_ticks = max_ticks
    sim.chunk_size = chunk_size
    sim.sim_time_after_chunked_run = sim_time_after
    return sim


def run_full_history_simulation_until_extinguished_chunked_to_disk(
    max_ticks: int = DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    out_dir = None,
    start_fire_at_coord: Tuple[int, int, int] = DEFAULT_START_FIRE_AT_COORD,
    probabilistic: bool = DEFAULT_PROBABILISTIC,
    save_full_history: bool = DEFAULT_SAVE_FULL_HISTORY,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
    fire_dept_arrival_coords: Tuple[int, int, int] = DEFAULT_FIRE_DEPT_ARRIVAL_COORDS,
    fire_dept_response_time: float = DEFAULT_FIRE_DEPT_RESPONSE_TIME,
    verbose: bool = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
    random_seed: Optional[int] = None,
):
    """Run until extinguished in chunks, saving and clearing history after each chunk."""
    sim = run_sample_simulation(
        nr_ticks=0,
        start_fire_at_coord=start_fire_at_coord,
        probabilistic=probabilistic,
        save_full_history=save_full_history,
        snapshot_interval=snapshot_interval,
        save_history_parameters=ALL_HISTORY_PARAMETERS,
        fire_dept_arrival_coords=fire_dept_arrival_coords,
        fire_dept_response_time=fire_dept_response_time,
        random_seed=random_seed,
    )

    extinguished, sim_time_after = run_and_save_sim_in_chunks_until_extinguished(
        sim=sim,
        chunk_size=chunk_size,
        out_dir=out_dir,
        max_total_ticks=max_ticks,
        verbose=verbose,
    )
    sim.extinguished = extinguished
    sim.until_extinguished_max_ticks = max_ticks
    sim.chunk_size = chunk_size
    sim.sim_time_after_chunked_run = sim_time_after
    return sim
