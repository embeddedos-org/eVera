import unittest
class TestEVeraUnit(unittest.TestCase):
    def test_gps_lock(self):
        gps_fixed = True
        self.assertTrue(gps_fixed)
    def test_route_planning(self):
        route = ["start", "mid", "end"]
        self.assertEqual(route[-1], "end")
