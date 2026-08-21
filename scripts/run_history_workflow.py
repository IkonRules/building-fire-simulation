"""Run long, full-history or disk-backed workflows for the sample world."""

from building_fire_simulation.scenarios import (
    run_full_history_simulation,
    run_full_history_simulation_until_extinguished,
    run_full_history_simulation_fixed_ticks_chunked,
    run_full_history_simulation_until_extinguished_chunked,
    run_full_history_simulation_until_extinguished_chunked_to_disk,
)
from building_fire_simulation.simulation_settings import (
    ALL_HISTORY_PARAMETERS,
    RUN_MODE_OPTIONS,
    DEFAULT_RUN_MODE,
    DEFAULT_NR_TICKS,
    DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PROBABILISTIC,
    DEFAULT_SAVE_FULL_HISTORY,
    DEFAULT_SNAPSHOT_INTERVAL,
    DEFAULT_UNTIL_EXTINGUISHED_VERBOSE,
)


# -------------------------------------------------------------------------
# SIMULATION SETTINGS
# -------------------------------------------------------------------------

# Available run modes:
#   "fixed_ticks"
#   "until_extinguished"
#   "fixed_ticks_chunked"
#   "until_extinguished_chunked"
#   "until_extinguished_chunked_to_disk"
RUN_MODE = DEFAULT_RUN_MODE
# Alternatives:
# RUN_MODE = "fixed_ticks"
# RUN_MODE = "until_extinguished"
# RUN_MODE = "fixed_ticks_chunked"
# RUN_MODE = "until_extinguished_chunked"
# RUN_MODE = "until_extinguished_chunked_to_disk"

# Number of simulation ticks when RUN_MODE is "fixed_ticks" or "fixed_ticks_chunked".
NR_TICKS = DEFAULT_NR_TICKS
# Alternatives:
# NR_TICKS = 30       # quick smoke test
# NR_TICKS = 1000     # longer run

# Maximum additional ticks when using one of the until-extinguished modes.
MAX_TICKS_UNTIL_EXTINGUISHED = DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED
# Alternatives:
# MAX_TICKS_UNTIL_EXTINGUISHED = 1000
# MAX_TICKS_UNTIL_EXTINGUISHED = 10000

# Chunk size for chunked modes.
CHUNK_SIZE = DEFAULT_CHUNK_SIZE
# Alternatives:
# CHUNK_SIZE = 100
# CHUNK_SIZE = 2000

# Where the initial fire starts.
START_FIRE_AT_COORD = (0, 0, 0)
# Alternatives:
# START_FIRE_AT_COORD = (1, 1, 0)
# START_FIRE_AT_COORD = (2, 0, 0)

# Probabilistic simulation setting.
# True  = probabilistic devices/parameters are enabled where supported.
# False = fixed-parameter run; probabilistic device sampling is skipped.
PROBABILISTIC = DEFAULT_PROBABILISTIC
# Alternative fixed-parameter setting:
# PROBABILISTIC = False

# Seed Python and supported NumPy draws for repeatable exploratory runs.
RANDOM_SEED = 2026

# Whether to save history snapshots.
SAVE_FULL_HISTORY = DEFAULT_SAVE_FULL_HISTORY
# Alternative lighter setting:
# SAVE_FULL_HISTORY = False

# How often to save snapshots.
# 1 saves every tick. Larger values save less data.
SNAPSHOT_INTERVAL = DEFAULT_SNAPSHOT_INTERVAL
# Alternatives:
# SNAPSHOT_INTERVAL = 5
# SNAPSHOT_INTERVAL = 10

# Fire department settings.
FIRE_DEPT_ARRIVAL_COORDS = (4, 4, 0)
FIRE_DEPT_RESPONSE_TIME = 240
# Alternatives:
# FIRE_DEPT_RESPONSE_TIME = 60
# FIRE_DEPT_RESPONSE_TIME = 999999

# Print progress for chunked / until-extinguished runners.
VERBOSE = DEFAULT_UNTIL_EXTINGUISHED_VERBOSE
# Alternative quiet setting:
# VERBOSE = False

# Used only by RUN_MODE == "until_extinguished_chunked_to_disk".
# None means use the default project data folder. Existing files may be replaced.
CHUNK_OUTPUT_DIR = None
# Alternative repository-relative folder:
# CHUNK_OUTPUT_DIR = "outputs/chunks"


# -------------------------------------------------------------------------
# RUN SIMULATION
# -------------------------------------------------------------------------

if RUN_MODE not in RUN_MODE_OPTIONS:
    raise ValueError(f"Unknown RUN_MODE={RUN_MODE!r}. Valid options: {RUN_MODE_OPTIONS}")

if RUN_MODE == "fixed_ticks":
    sim = run_full_history_simulation(
        nr_ticks=NR_TICKS,
        start_fire_at_coord=START_FIRE_AT_COORD,
        probabilistic=PROBABILISTIC,
        save_full_history=SAVE_FULL_HISTORY,
        snapshot_interval=SNAPSHOT_INTERVAL,
        fire_dept_arrival_coords=FIRE_DEPT_ARRIVAL_COORDS,
        fire_dept_response_time=FIRE_DEPT_RESPONSE_TIME,
        random_seed=RANDOM_SEED,
    )

elif RUN_MODE == "until_extinguished":
    sim = run_full_history_simulation_until_extinguished(
        max_ticks=MAX_TICKS_UNTIL_EXTINGUISHED,
        start_fire_at_coord=START_FIRE_AT_COORD,
        probabilistic=PROBABILISTIC,
        save_full_history=SAVE_FULL_HISTORY,
        snapshot_interval=SNAPSHOT_INTERVAL,
        fire_dept_arrival_coords=FIRE_DEPT_ARRIVAL_COORDS,
        fire_dept_response_time=FIRE_DEPT_RESPONSE_TIME,
        verbose=VERBOSE,
        random_seed=RANDOM_SEED,
    )

elif RUN_MODE == "fixed_ticks_chunked":
    sim = run_full_history_simulation_fixed_ticks_chunked(
        nr_ticks=NR_TICKS,
        chunk_size=CHUNK_SIZE,
        start_fire_at_coord=START_FIRE_AT_COORD,
        probabilistic=PROBABILISTIC,
        save_full_history=SAVE_FULL_HISTORY,
        snapshot_interval=SNAPSHOT_INTERVAL,
        fire_dept_arrival_coords=FIRE_DEPT_ARRIVAL_COORDS,
        fire_dept_response_time=FIRE_DEPT_RESPONSE_TIME,
        verbose=VERBOSE,
        random_seed=RANDOM_SEED,
    )

elif RUN_MODE == "until_extinguished_chunked":
    sim = run_full_history_simulation_until_extinguished_chunked(
        max_ticks=MAX_TICKS_UNTIL_EXTINGUISHED,
        chunk_size=CHUNK_SIZE,
        start_fire_at_coord=START_FIRE_AT_COORD,
        probabilistic=PROBABILISTIC,
        save_full_history=SAVE_FULL_HISTORY,
        snapshot_interval=SNAPSHOT_INTERVAL,
        fire_dept_arrival_coords=FIRE_DEPT_ARRIVAL_COORDS,
        fire_dept_response_time=FIRE_DEPT_RESPONSE_TIME,
        verbose=VERBOSE,
        random_seed=RANDOM_SEED,
    )

elif RUN_MODE == "until_extinguished_chunked_to_disk":
    sim = run_full_history_simulation_until_extinguished_chunked_to_disk(
        max_ticks=MAX_TICKS_UNTIL_EXTINGUISHED,
        chunk_size=CHUNK_SIZE,
        out_dir=CHUNK_OUTPUT_DIR,
        start_fire_at_coord=START_FIRE_AT_COORD,
        probabilistic=PROBABILISTIC,
        save_full_history=SAVE_FULL_HISTORY,
        snapshot_interval=SNAPSHOT_INTERVAL,
        fire_dept_arrival_coords=FIRE_DEPT_ARRIVAL_COORDS,
        fire_dept_response_time=FIRE_DEPT_RESPONSE_TIME,
        verbose=VERBOSE,
        random_seed=RANDOM_SEED,
    )


print("Simulation finished.")
print(f"Run mode: {RUN_MODE}")
print(f"Final tick: {sim.time}")
print(f"Probabilistic: {sim.probabilistic}")
print(f"Save full history: {sim.save_full_history}")
print(f"Snapshot interval: {SNAPSHOT_INTERVAL}")
print(f"History fields: {ALL_HISTORY_PARAMETERS}")
print(f"Saved snapshots currently in memory: {len(sim.history)}")

if RUN_MODE in ("fixed_ticks", "fixed_ticks_chunked"):
    print(f"Requested fixed ticks: {NR_TICKS}")

if RUN_MODE in (
    "until_extinguished",
    "until_extinguished_chunked",
    "until_extinguished_chunked_to_disk",
):
    print(f"Max ticks until extinguished: {MAX_TICKS_UNTIL_EXTINGUISHED}")
    print(f"Extinguished before max ticks: {getattr(sim, 'extinguished', None)}")

if "chunked" in RUN_MODE:
    print(f"Chunk size: {CHUNK_SIZE}")

if sim.history:
    first_tick = min(sim.history)
    last_tick = max(sim.history)
    print(f"First saved tick: {first_tick}")
    print(f"Last saved tick: {last_tick}")
    print(f"Fields in first snapshot: {tuple(sim.history[first_tick].keys())}")
