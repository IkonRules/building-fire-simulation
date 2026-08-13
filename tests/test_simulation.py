import unittest

from fire_building_sim.fire_simulation import FireSimulation
from fire_building_sim.scenarios import build_sample_world, run_sample_simulation


class FireSimulationTests(unittest.TestCase):
    def test_explicit_ignition_and_history_progression(self):
        sim = run_sample_simulation(
            nr_ticks=5,
            probabilistic=False,
            save_full_history=True,
            snapshot_interval=1,
            random_seed=7,
        )
        self.assertEqual(sim.time, 5)
        self.assertTrue(sim.history[0]["fire_status"][(0, 0, 0)].is_on_fire)
        self.assertEqual(sorted(sim.history), [0, 1, 2, 3, 4])

    def test_cool_building_does_not_spontaneously_ignite(self):
        model, _, _ = build_sample_world()
        sim = FireSimulation(model, save_full_history=False, agents=[], probabilistic=False)
        sim._update_ignition_status()
        sim._try_ignite_new_cubes(verbose=False)
        self.assertFalse(any(state.is_on_fire for state in sim.fire_status.values()))

    def test_seeded_probabilistic_run_is_reproducible(self):
        def signature():
            sim = run_sample_simulation(
                nr_ticks=12,
                probabilistic=True,
                save_full_history=True,
                snapshot_interval=1,
                random_seed=2026,
            )
            last = sim.history[max(sim.history)]
            temperatures = tuple(round(last["air_temp"][coord], 8) for coord in sorted(last["air_temp"]))
            agents = tuple((agent["name"], agent["location"]) for agent in last["agents"])
            fires = tuple(coord for coord, state in sorted(last["fire_status"].items()) if state.is_on_fire)
            return temperatures, agents, fires

        self.assertEqual(signature(), signature())

    def test_agent_positions_remain_inside_the_building(self):
        sim = run_sample_simulation(
            nr_ticks=15,
            probabilistic=False,
            save_full_history=True,
            snapshot_interval=1,
            random_seed=11,
        )
        self.assertTrue(sim._movement_hook_installed)
        john_locations = []
        for snapshot in sim.history.values():
            for agent in snapshot["agents"]:
                self.assertIn(agent["location"], sim.global_model)
                if agent["name"] == "John":
                    john_locations.append(agent["location"])
        self.assertGreater(len(set(john_locations)), 1)

    def test_fire_department_respects_configured_response_time(self):
        sim = run_sample_simulation(
            nr_ticks=0,
            probabilistic=False,
            save_full_history=False,
            fire_dept_response_time=3,
            random_seed=3,
        )
        department = sim.fire_department
        department.receive_alarm([(0, 0, 0)], now_s=0)
        department.step(dt_s=2, now_s=0)
        self.assertFalse(department.units[0].arrived)
        department.step(dt_s=1, now_s=2)
        self.assertTrue(department.units[0].arrived)


if __name__ == "__main__":
    unittest.main()
