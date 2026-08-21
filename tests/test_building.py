import unittest

from building_fire_simulation.scenarios import build_sample_world


class SampleBuildingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.room_catalogue, cls.agents = build_sample_world()

    def test_sample_building_has_two_complete_floors(self):
        self.assertEqual(len(self.model), 50)
        self.assertEqual({coord[2] for coord in self.model}, {0, 1})
        self.assertIn((0, 0, 0), self.model)
        self.assertIn((4, 4, 1), self.model)

    def test_adjoining_surfaces_are_reciprocal(self):
        left = self.model[(1, 2, 0)].left_wall
        right = self.model[(0, 2, 0)].right_wall
        self.assertIs(left.surface_neighbor, right)
        self.assertIs(right.surface_neighbor, left)

    def test_room_catalogue_only_contains_valid_coordinates(self):
        self.assertGreaterEqual(len(self.room_catalogue), 5)
        for coords in self.room_catalogue.values():
            self.assertTrue(coords)
            self.assertTrue(all(coord in self.model for coord in coords))


if __name__ == "__main__":
    unittest.main()
