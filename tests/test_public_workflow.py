import unittest

import pandas as pd

from building_fire_simulation.fire_analysis import agent_routes, fd_actions_dataframe
from building_fire_simulation.scenarios import run_custom_simulation


class PublicWorkflowTests(unittest.TestCase):
    def test_recorded_history_is_consumable_by_analysis_helpers(self):
        sim = run_custom_simulation(
            nr_ticks=3,
            start_fire_at_coord=(0, 0, 0),
            probabilistic=False,
            save_full_history=True,
            snapshot_interval=1,
            save_history_parameters=(
                "fire_status",
                "air_temp",
                "components",
                "agents",
                "fire_department",
            ),
            fire_dept_arrival_coords=(4, 4, 0),
            fire_dept_response_time=30,
            random_seed=2026,
        )

        routes = agent_routes(sim)
        actions = fd_actions_dataframe(sim)

        self.assertEqual(list(routes.index), [0, 1, 2])
        self.assertEqual(set(routes.columns), {"Elin", "John"})
        self.assertIsInstance(actions, pd.DataFrame)
        self.assertIn("components", sim.history[0])


if __name__ == "__main__":
    unittest.main()
