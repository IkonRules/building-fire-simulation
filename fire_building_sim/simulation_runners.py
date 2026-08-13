"""Simulation execution strategies.

This module contains functions that ADVANCE an existing FireSimulation object.
They are not analysis functions: they mutate the simulation by calling sim.tick().

Use this module for run modes such as:
    - fixed number of ticks
    - until fire is extinguished
    - chunked fixed runs
    - chunked until-extinguished runs
"""
from __future__ import annotations

import os
import pickle
from typing import Optional, Tuple

from fire_building_sim.config import DATA_DIR


def is_fire_extinguished(sim) -> bool:
    """Return True if the simulation currently has no burning cubes."""
    if hasattr(sim, "get_burning_cubes"):
        return len(sim.get_burning_cubes()) == 0

    # Legacy fallback. This is less reliable than sim.get_burning_cubes().
    burning_coords = [
        coord
        for coord, fire_state in getattr(sim, "fire_status", {}).items()
        if getattr(fire_state, "is_on_fire", False)
    ]
    return len(burning_coords) == 0


def get_burning_coord_count(sim) -> int:
    """Return the number of currently burning cubes."""
    if hasattr(sim, "get_burning_cubes"):
        return len(sim.get_burning_cubes())

    return len([
        coord
        for coord, fire_state in getattr(sim, "fire_status", {}).items()
        if getattr(fire_state, "is_on_fire", False)
    ])


def run_for_n_ticks(sim, nr_ticks: int, verbose: bool = False, print_every: Optional[int] = None):
    """Advance an existing simulation a fixed number of ticks.

    Parameters
    ----------
    sim:
        Existing FireSimulation object.
    nr_ticks:
        Number of ticks to advance.
    verbose:
        If True, print progress.
    print_every:
        Optional progress interval. If None and verbose=True, defaults to 100.

    Returns
    -------
    sim
        The same simulation object, after being advanced.
    """
    if nr_ticks < 0:
        raise ValueError("nr_ticks must be non-negative")

    if print_every is None:
        print_every = 100

    for _ in range(nr_ticks):
        sim.tick()
        if verbose and print_every and sim.time % print_every == 0:
            print(f"Simulation reached {sim.time} ticks.")

    return sim


def run_fire_until_extinguished(
    sim,
    max_ticks: int,
    time_int: int = 2000,
    verbose: bool = False,
) -> bool:
    """Run until no cubes are burning, or until max_ticks has been advanced.

    Parameters
    ----------
    sim:
        Existing FireSimulation object.
    max_ticks:
        Maximum number of additional ticks to run.
    time_int:
        Progress print interval based on sim.time.
    verbose:
        If True, print burning-cube counts and status messages.

    Returns
    -------
    bool
        True if the fire was extinguished before the max tick cap, else False.
    """
    if max_ticks < 0:
        raise ValueError("max_ticks must be non-negative")

    tick_count = 0
    start_time = getattr(sim, "time", 0)

    while tick_count < max_ticks:
        burning_count = get_burning_coord_count(sim)

        if verbose:
            ts = start_time + tick_count
            print(f"Timestep {ts}: {burning_count} burning cubes")

        if burning_count == 0:
            if verbose:
                print("All fires extinguished.")
            return True

        sim.tick()
        tick_count += 1

        if time_int and sim.time % time_int == 0:
            print(f"Simulation reached ({sim.time}) ticks.")

    if verbose:
        print(f"Simulation stopped: reached max_ticks={max_ticks}.")

    return is_fire_extinguished(sim)


def run_sim_in_chunks(
    sim,
    total_ticks: int,
    chunk_size: int = 5000,
    verbose: bool = False,
) -> Tuple[bool, int]:
    """Run a fixed total number of ticks in chunks.

    This is useful when you want progress output or want to keep the execution
    pattern similar to the until-extinguished chunked runner.

    Returns
    -------
    tuple[bool, int]
        (completed, sim_time_after)
    """
    if total_ticks < 0:
        raise ValueError("total_ticks must be non-negative")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    remaining = total_ticks
    while remaining > 0:
        this_chunk = min(chunk_size, remaining)
        t0 = getattr(sim, "time", 0)
        run_for_n_ticks(sim, this_chunk, verbose=verbose)
        ran = getattr(sim, "time", 0) - t0

        if verbose:
            print(f"Ran chunk of {ran} ticks. sim.time={getattr(sim, 'time', 0)}")

        if ran <= 0:
            if verbose:
                print("No progress this chunk; stopping to avoid an infinite loop.")
            return False, getattr(sim, "time", 0)

        remaining -= ran

    return True, getattr(sim, "time", 0)


def run_sim_in_chunks_until_extinguished(
    sim,
    chunk_size: int = 5000,
    max_total_ticks: Optional[int] = None,
    verbose: bool = False,
) -> Tuple[bool, int]:
    """Run repeated chunks until the fire is extinguished.

    Parameters
    ----------
    sim:
        Existing FireSimulation object.
    chunk_size:
        Number of ticks to run per chunk.
    max_total_ticks:
        Optional global safety cap. If None, chunks continue until extinguished
        or until no progress is made.
    verbose:
        If True, print progress.

    Returns
    -------
    tuple[bool, int]
        (extinguished, sim_time_after)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_total_ticks is not None and max_total_ticks < 0:
        raise ValueError("max_total_ticks must be non-negative or None")

    start_time = getattr(sim, "time", 0)

    while True:
        elapsed = getattr(sim, "time", 0) - start_time
        if max_total_ticks is not None and elapsed >= max_total_ticks:
            return is_fire_extinguished(sim), getattr(sim, "time", 0)

        remaining_cap = None
        if max_total_ticks is not None:
            remaining_cap = max_total_ticks - elapsed

        this_chunk = chunk_size if remaining_cap is None else min(chunk_size, remaining_cap)
        t0 = getattr(sim, "time", 0)
        extinguished = run_fire_until_extinguished(sim, this_chunk, verbose=verbose)
        ran = getattr(sim, "time", 0) - t0

        if extinguished:
            return True, getattr(sim, "time", 0)

        if ran <= 0:
            if verbose:
                print("No progress this chunk; stopping to avoid an infinite loop.")
            return False, getattr(sim, "time", 0)


def run_and_save_sim_in_chunks_until_extinguished(
    sim,
    chunk_size: int = 5000,
    out_dir: Optional[str] = None,
    max_total_ticks: Optional[int] = None,
    verbose: bool = False,
) -> Tuple[bool, int]:
    """Run until extinguished in chunks and save history after each chunk.

    After each chunk, sim.history is saved to snapshot_data_{chunk_nr}.pkl and
    then cleared in-place to reduce memory use.

    Returns
    -------
    tuple[bool, int]
        (extinguished, sim_time_after)
    """
    if out_dir is None:
        out_dir = DATA_DIR

    os.makedirs(out_dir, exist_ok=True)
    start_time = getattr(sim, "time", 0)
    chunk_nr = 0

    while True:
        elapsed = getattr(sim, "time", 0) - start_time
        if max_total_ticks is not None and elapsed >= max_total_ticks:
            return is_fire_extinguished(sim), getattr(sim, "time", 0)

        remaining_cap = None
        if max_total_ticks is not None:
            remaining_cap = max_total_ticks - elapsed

        this_chunk = chunk_size if remaining_cap is None else min(chunk_size, remaining_cap)
        t0 = getattr(sim, "time", 0)
        extinguished = run_fire_until_extinguished(sim, this_chunk, verbose=verbose)

        if getattr(sim, "history", None):
            if len(sim.history) > 0:
                file_path = os.path.join(out_dir, f"snapshot_data_{chunk_nr}.pkl")
                with open(file_path, "wb") as f:
                    pickle.dump(sim.history, f, protocol=pickle.HIGHEST_PROTOCOL)
                if verbose:
                    print(f"Saved {len(sim.history)} snapshots -> {file_path}")
                sim.history.clear()

        ran = getattr(sim, "time", 0) - t0

        if extinguished:
            if verbose:
                print(f"Fire extinguished at sim.time={getattr(sim, 'time', 0)}.")
            return True, getattr(sim, "time", 0)

        if ran <= 0:
            if verbose:
                print("No progress this chunk; stopping to avoid an infinite loop.")
            return False, getattr(sim, "time", 0)

        chunk_nr += 1
