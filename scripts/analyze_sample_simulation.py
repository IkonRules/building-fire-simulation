"""Open interactive analysis views for a longer sample simulation."""

from building_fire_simulation.fire_analysis import (
    agent_routes,
    calculate_inventory_loss,
    fd_actions_dataframe,
    plot_air_temp_in_cubes,
    plot_heat_output_in_cube,
    plot_item_energy_left_in_cube,
    visualize_building_with_fire,
)
from building_fire_simulation.scenarios import run_custom_simulation


SEED = 2026
TICKS = 500
IGNITION_COORD = (0, 0, 0)
HISTORY_FIELDS = (
    "fire_status",
    "air_temp",
    "components",
    "agents",
    "fire_department",
)


def main() -> None:
    sim = run_custom_simulation(
        nr_ticks=TICKS,
        start_fire_at_coord=IGNITION_COORD,
        probabilistic=False,
        save_full_history=True,
        snapshot_interval=1,
        save_history_parameters=HISTORY_FIELDS,
        fire_dept_arrival_coords=(4, 4, 0),
        fire_dept_response_time=240,
        random_seed=SEED,
    )

    routes = agent_routes(sim)
    fire_department_actions = fd_actions_dataframe(sim)
    active_inventory_value = calculate_inventory_loss(sim, sim.global_model)

    print("Agent routes:")
    print(routes.tail())
    print("\nFire-department actions:")
    print(fire_department_actions.head())
    print(f"\nActive flammable inventory value at the end: {active_inventory_value:.2f}")

    coords = [IGNITION_COORD, (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    plot_air_temp_in_cubes(sim, coords)
    plot_item_energy_left_in_cube(sim, IGNITION_COORD)
    plot_heat_output_in_cube(sim, IGNITION_COORD)

    for tick in (0, 15, 100, 200, TICKS - 1):
        visualize_building_with_fire(sim, sim.global_model, tick)


if __name__ == "__main__":
    main()
