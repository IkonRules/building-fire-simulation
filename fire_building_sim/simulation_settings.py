"""Named simulation settings for reusable runner scripts.

This file is intentionally simple. It is a good place to keep reusable
settings presets without hiding the values from the user.
"""
from __future__ import annotations

# All history fields currently supported by FireSimulation.save_state_snapshot().
ALL_HISTORY_PARAMETERS = (
    "fire_status",       # FireState object for every cube.
    "air_temp",          # Air temperature for every cube.
    "components",        # Surfaces, cover materials, items, and degradation state.
    "agents",            # Agent locations and attributes.
    "fire_department",   # Fire department units, command state, and response telemetry.
)

# Lightweight default for quick tests.
BASIC_HISTORY_PARAMETERS = (
    "fire_status",
    "agents",
    "air_temp",
)

# Common simulation presets.
DEFAULT_NR_TICKS = 300
DEFAULT_START_FIRE_AT_COORD = (0, 0, 0)
DEFAULT_FIRE_DEPT_ARRIVAL_COORDS = (4, 4, 4)
DEFAULT_FIRE_DEPT_RESPONSE_TIME = 240

# Snapshot interval:
#   1  = save every tick, best for debugging/analysis.
#   5  = save every 5 ticks.
#   10 = save every 10 ticks, lighter memory usage.
DEFAULT_SNAPSHOT_INTERVAL = 1

# Run mode options:
#   "fixed_ticks"                       = run exactly DEFAULT_NR_TICKS ticks.
#   "until_extinguished"                = run until no cubes are burning, capped by DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED.
#   "fixed_ticks_chunked"               = run a fixed number of ticks in chunks.
#   "until_extinguished_chunked"        = run until extinguished in repeated chunks.
#   "until_extinguished_chunked_to_disk"= run until extinguished in chunks and save history to disk after each chunk.
RUN_MODE_OPTIONS = (
    "fixed_ticks",
    "until_extinguished",
    "fixed_ticks_chunked",
    "until_extinguished_chunked",
    "until_extinguished_chunked_to_disk",
)

DEFAULT_RUN_MODE = "fixed_ticks"
# Alternative examples:
# DEFAULT_RUN_MODE = "until_extinguished"
# DEFAULT_RUN_MODE = "fixed_ticks_chunked"
# DEFAULT_RUN_MODE = "until_extinguished_chunked"
# DEFAULT_RUN_MODE = "until_extinguished_chunked_to_disk"

# Safety cap for until-extinguished simulations.
DEFAULT_MAX_TICKS_UNTIL_EXTINGUISHED = 5000

# Chunk size for chunked runners.
DEFAULT_CHUNK_SIZE = 500
# Alternative lighter memory / more frequent saves:
# DEFAULT_CHUNK_SIZE = 100
# Alternative faster, larger chunks:
# DEFAULT_CHUNK_SIZE = 2000

# Whether helper functions should print progress while running until extinguished.
DEFAULT_UNTIL_EXTINGUISHED_VERBOSE = True

# Simulation behavior defaults.
DEFAULT_PROBABILISTIC = True
# Alternative deterministic setting:
# DEFAULT_PROBABILISTIC = False

DEFAULT_SAVE_FULL_HISTORY = True
# Alternative lighter setting:
# DEFAULT_SAVE_FULL_HISTORY = False
