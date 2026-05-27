import unittest

class TesteVeraSimulation(unittest.TestCase):
    def test_gps_receiver_lock_simulation(self):
        # Simulate GPS hardware locking on to satellites
        GPS_STATUS = "SEARCHING"
        satellites_found = 0
        for i in range(12):
            satellites_found += 1
        if satellites_found >= 4:
            GPS_STATUS = "LOCKED"
        assert GPS_STATUS == "LOCKED", "GPS receiver lock simulation failed"
