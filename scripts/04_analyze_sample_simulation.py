import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fire_building_sim.scenarios import (
    run_sample_simulation, run_full_history_simulation, run_custom_simulation
    )
from  fire_building_sim.fire_analysis import (
    # Agents and actors
    agent_routes, fd_actions_dataframe,
    
    # Monetary 
    calculate_inventory_loss,
    
    # Cube stats
    plot_air_temp_in_cubes,
    plot_item_energy_left_in_cube,
    plot_heat_output_in_cube,
    
    # Vizualize building
    visualize_building_with_fire
    )

# Run custom simulation
sim = run_custom_simulation(
    nr_ticks = 200,
    start_fire_at_coord = (0, 0, 0),
    probabilistic = True,
    save_full_history = True,
    snapshot_interval = 1,
    save_history_parameters = ("fire_status",
                               "air_temp",
                               "components", 
                               "agents",
                               "fire_department"),
    fire_dept_arrival_coords = (4, 4, 4),
    fire_dept_response_time = 240,
    random_seed = 2026
    )

# Agents and actors
agent_movements = agent_routes(sim)
fd_actions = fd_actions_dataframe(sim).head()
print(fd_actions)

# Monetary
loss = calculate_inventory_loss(sim, sim.global_model)

# Cube stats
coords = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
air_temps = plot_air_temp_in_cubes(sim, coords)
item_energy = plot_item_energy_left_in_cube(sim, (0,0,0))
item_heat_output = plot_heat_output_in_cube(sim, (0,0,0))


# Vizualize building
visualize_building_with_fire(sim, sim.global_model, 199)


# fire_status = sim.history[0]['fire_status']
# air_temp = sim.history[0]['air_temp']
# components = sim.history[0]['components']
# agents = sim.history[0]['agents']
# fire_department = sim.history[0]['fire_department']



