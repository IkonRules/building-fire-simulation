import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fire_building_sim.scenarios import save_default_data

global_model, room_catalogue = save_default_data()
print(f"Saved sample building with {len(global_model)} cubes.")
print(f"Saved room catalogue with {len(room_catalogue)} categories.")
