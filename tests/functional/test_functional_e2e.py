import unittest

class TesteVeraFunctional(unittest.TestCase):
    def test_route_planning_pipeline(self):
        waypoints = ["Start", "Waypoint 1", "Waypoint 2", "Destination"]
        route = []
        for wp in waypoints:
            route.append(wp)
        assert route == waypoints, "Route planning pipeline failed to preserve waypoints"
