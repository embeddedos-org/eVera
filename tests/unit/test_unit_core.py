import unittest

class TesteVeraUnit(unittest.TestCase):
    def test_gps_coordinate_distance_calculation(self):
        # Test Haversine formula for distance between coordinates
        import math
        lat1, lon1 = 37.7749, -122.4194 # San Francisco
        lat2, lon2 = 34.0522, -118.2437 # Los Angeles
        R = 6371.0 # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        dist = R * c
        assert abs(dist - 559.1) < 10.0, f"Distance calculated as {dist:.1f}km instead of ~559km"
