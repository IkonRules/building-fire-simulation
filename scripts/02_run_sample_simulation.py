import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fire_building_sim.scenarios import run_sample_simulation

sim = run_sample_simulation(nr_ticks=300, random_seed=2026)
print(f"Simulation finished at tick {sim.time}.")
print(f"Saved snapshots: {len(sim.history)}")
