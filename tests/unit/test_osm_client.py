import unittest
from evera.location.osm_client import OSMNominatimClient

class TestOSMNominatimClient(unittest.TestCase):
    def test_osm_nominatim_reverse_geocode(self):
        client = OSMNominatimClient()
        res = client.reverse_geocode(37.7749, -122.4194)
        assert res["status"] in ["success", "fallback"]
        assert res["city"] == "San Francisco"
