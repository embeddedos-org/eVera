import requests
import urllib.parse

class VeraGeolocator:
    """
    World-class Geolocation client using OpenStreetMap/Nominatim API
    for autonomous vehicle navigation.
    """
    def __init__(self, user_agent="VeraAutonomousVehicle/1.0"):
        self.base_url = "https://nominatim.openstreetmap.org/reverse"
        self.headers = {"User-Agent": user_agent}

    def reverse_geocode(self, lat: float, lon: float) -> dict:
        """
        Resolve GPS coordinates to a physical address using OSM Nominatim.
        """
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 18,
            "addressdetails": 1
        }
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def forward_geocode(self, address: str) -> dict:
        """
        Resolve a physical address to GPS coordinates.
        """
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                results = response.json()
                if results:
                    return {
                        "lat": float(results[0]["lat"]),
                        "lon": float(results[0]["lon"]),
                        "display_name": results[0]["display_name"]
                    }
                return {"error": "No results found"}
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
