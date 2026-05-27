
import urllib.request
import json
import time

class OSMNominatimClient:
    def __init__(self, user_agent="eVera-Autonomous-Agent/1.0"):
        self.user_agent = user_agent
        self.base_url = "https://nominatim.openstreetmap.org/reverse"
        
    def reverse_geocode(self, lat, lon):
        """
        Reverse geocode latitude/longitude to a real-world address using OpenStreetMap Nominatim.
        Nominatim is selected as the world's best public open-source location API.
        """
        url = f"{self.base_url}?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": self.user_agent}
        )
        try:
            # Respect OSM Nominatim usage policy (max 1 request per second)
            time.sleep(1.0)
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode())
                return {
                    "display_name": res_data.get("display_name", "Unknown Location"),
                    "city": res_data.get("address", {}).get("city", ""),
                    "country": res_data.get("address", {}).get("country", ""),
                    "status": "success"
                }
        except Exception as e:
            return {
                "display_name": f"Mock Location ({lat:.4f}, {lon:.4f})",
                "city": "San Francisco",
                "country": "United States",
                "status": "fallback",
                "error": str(e)
            }
