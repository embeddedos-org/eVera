"""Home Controller Agent — controls IoT devices via Home Assistant API or local simulation."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

# Home Assistant config from env
HA_URL = os.getenv("VOCA_HA_URL", "").rstrip("/")  # e.g. http://homeassistant.local:8123
HA_TOKEN = os.getenv("VOCA_HA_TOKEN", "")


def _ha_available() -> bool:
    return bool(HA_URL and HA_TOKEN)


async def _ha_request(method: str, endpoint: str, data: dict | None = None) -> dict:
    """Make a request to the Home Assistant REST API."""
    import httpx
    url = f"{HA_URL}/api/{endpoint}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        else:
            resp = await client.post(url, headers=headers, json=data or {})
        resp.raise_for_status()
        return resp.json() if resp.text else {}


# --- Local simulation fallback ---

def _load_home_state() -> dict:
    path = DATA_DIR / "home_state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "lights": {"living_room": {"on": False, "brightness": 100}, "bedroom": {"on": False, "brightness": 100}, "kitchen": {"on": False, "brightness": 100}},
        "thermostat": {"temperature": 72, "mode": "auto"},
        "doors": {"front": "locked", "back": "locked", "garage": "locked"},
        "security": {"status": "armed", "alerts": []},
    }


def _save_home_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "home_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


class ControlLightTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="control_light",
            description="Control room lights (on, off, dim)",
            parameters={
                "room": {"type": "str", "description": "Room name (living_room, bedroom, kitchen)"},
                "action": {"type": "str", "description": "Action: on, off, dim"},
                "brightness": {"type": "int", "description": "Brightness 0-100 (for dim)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        room = kwargs.get("room", "living_room").lower().replace(" ", "_")
        action = kwargs.get("action", "on").lower()
        brightness = kwargs.get("brightness", 100)

        if _ha_available():
            try:
                entity_id = f"light.{room}"
                if action == "off":
                    await _ha_request("POST", "services/light/turn_off", {"entity_id": entity_id})
                else:
                    service_data: dict[str, Any] = {"entity_id": entity_id}
                    if action == "dim":
                        service_data["brightness_pct"] = brightness
                    await _ha_request("POST", "services/light/turn_on", service_data)
                return {"status": "success", "room": room, "action": action, "source": "home_assistant"}
            except Exception as e:
                logger.warning("HA light control failed: %s — using simulation", e)

        # Local simulation fallback
        home = _load_home_state()
        if room not in home["lights"]:
            home["lights"][room] = {"on": False, "brightness": 100}
        if action == "on":
            home["lights"][room]["on"] = True
        elif action == "off":
            home["lights"][room]["on"] = False
        elif action == "dim":
            home["lights"][room]["on"] = True
            home["lights"][room]["brightness"] = max(0, min(100, brightness))
        _save_home_state(home)
        return {"status": "success", "room": room, "light": home["lights"][room], "source": "simulation"}


class SetThermostatTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="set_thermostat",
            description="Set thermostat temperature and mode",
            parameters={
                "temperature": {"type": "float", "description": "Target temperature in °F"},
                "mode": {"type": "str", "description": "Mode: heat, cool, auto, off"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        temp = kwargs.get("temperature", 72)
        mode = kwargs.get("mode", "auto")

        if _ha_available():
            try:
                entity_id = "climate.thermostat"
                await _ha_request("POST", "services/climate/set_temperature", {
                    "entity_id": entity_id, "temperature": temp,
                })
                if mode != "auto":
                    await _ha_request("POST", "services/climate/set_hvac_mode", {
                        "entity_id": entity_id, "hvac_mode": mode,
                    })
                return {"status": "success", "temperature": temp, "mode": mode, "source": "home_assistant"}
            except Exception as e:
                logger.warning("HA thermostat failed: %s — using simulation", e)

        home = _load_home_state()
        home["thermostat"]["temperature"] = temp
        home["thermostat"]["mode"] = mode
        _save_home_state(home)
        return {"status": "success", "thermostat": home["thermostat"], "source": "simulation"}


class LockDoorTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="lock_door",
            description="Lock or unlock a door",
            parameters={
                "door": {"type": "str", "description": "Door: front, back, garage"},
                "action": {"type": "str", "description": "Action: lock, unlock"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        door = kwargs.get("door", "front").lower()
        action = kwargs.get("action", "lock").lower()

        if _ha_available():
            try:
                entity_id = f"lock.{door}_door"
                service = "lock" if action == "lock" else "unlock"
                await _ha_request("POST", f"services/lock/{service}", {"entity_id": entity_id})
                return {"status": "success", "door": door, "action": action, "source": "home_assistant"}
            except Exception as e:
                logger.warning("HA lock failed: %s — using simulation", e)

        home = _load_home_state()
        home["doors"][door] = "locked" if action == "lock" else "unlocked"
        _save_home_state(home)
        return {"status": "success", "door": door, "state": home["doors"][door], "source": "simulation"}


class CheckSecurityTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="check_security",
            description="Check home security status",
            parameters={"zone": {"type": "str", "description": "Zone: perimeter, interior, all"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if _ha_available():
            try:
                states = await _ha_request("GET", "states")
                security_entities = [
                    s for s in states
                    if any(domain in s.get("entity_id", "") for domain in ["alarm_control_panel", "binary_sensor.door", "binary_sensor.motion", "lock."])
                ]
                return {
                    "status": "success",
                    "entities": [{"id": s["entity_id"], "state": s["state"]} for s in security_entities[:20]],
                    "source": "home_assistant",
                }
            except Exception as e:
                logger.warning("HA security check failed: %s — using simulation", e)

        home = _load_home_state()
        return {
            "status": "success",
            "security": home["security"],
            "doors": home["doors"],
            "all_locked": all(v == "locked" for v in home["doors"].values()),
            "source": "simulation",
        }


class PlayMediaTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="play_media",
            description="Play media on a device",
            parameters={
                "media": {"type": "str", "description": "Media name or URI"},
                "device": {"type": "str", "description": "Target device"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        media = kwargs.get("media", "")
        device = kwargs.get("device", "default speaker")

        if _ha_available():
            try:
                entity_id = f"media_player.{device.replace(' ', '_')}"
                await _ha_request("POST", "services/media_player/play_media", {
                    "entity_id": entity_id,
                    "media_content_id": media,
                    "media_content_type": "music",
                })
                return {"status": "success", "playing": media, "device": device, "source": "home_assistant"}
            except Exception as e:
                logger.warning("HA media play failed: %s — using simulation", e)

        return {"status": "success", "playing": media, "device": device, "source": "simulation", "note": "Simulated — set VOCA_HA_URL and VOCA_HA_TOKEN for real playback"}


class GetDevicesTool(Tool):
    """List all available smart home devices from Home Assistant."""

    def __init__(self) -> None:
        super().__init__(
            name="list_devices",
            description="List all available smart home devices",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if _ha_available():
            try:
                states = await _ha_request("GET", "states")
                devices = [
                    {"id": s["entity_id"], "state": s["state"], "name": s.get("attributes", {}).get("friendly_name", "")}
                    for s in states
                    if any(s["entity_id"].startswith(d) for d in ["light.", "switch.", "climate.", "lock.", "media_player.", "cover.", "fan."])
                ]
                return {"status": "success", "devices": devices, "count": len(devices), "source": "home_assistant"}
            except Exception as e:
                logger.warning("HA device list failed: %s", e)

        home = _load_home_state()
        devices = []
        for room, state in home["lights"].items():
            devices.append({"id": f"light.{room}", "state": "on" if state["on"] else "off", "name": room})
        devices.append({"id": "climate.thermostat", "state": f"{home['thermostat']['temperature']}°F", "name": "Thermostat"})
        for door, state in home["doors"].items():
            devices.append({"id": f"lock.{door}", "state": state, "name": f"{door} door"})
        return {"status": "success", "devices": devices, "count": len(devices), "source": "simulation"}


class HomeControllerAgent(BaseAgent):
    """Controls IoT devices via Home Assistant API or local simulation."""

    name = "home_controller"
    description = "Controls IoT devices, lights, thermostat, locks, and media"
    tier = ModelTier.EXECUTOR

    ha_status = "connected to Home Assistant" if _ha_available() else "simulation mode (set VOCA_HA_URL and VOCA_HA_TOKEN for real devices)"

    system_prompt = (
        "You are a smart home controller. You manage lights, thermostat, door locks, "
        "security, and media playback. Use your tools to execute commands. "
        f"Current status: {ha_status}. "
        "When the user says 'turn on the lights', call control_light. "
        "When they mention temperature, use set_thermostat. "
        "For door locks, use lock_door. For security checks, use check_security. "
        "Use list_devices to show all available devices. "
        "Be direct and confirm actions taken."
    )

    offline_responses = {
        "light": "💡 Let me handle that light for you!",
        "thermostat": "🌡️ Adjusting the thermostat!",
        "temperature": "🌡️ Setting the temperature!",
        "lock": "🔒 Handling the door lock!",
        "music": "🎵 Let me play that for you!",
        "security": "🔐 Checking security status!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            ControlLightTool(),
            SetThermostatTool(),
            LockDoorTool(),
            CheckSecurityTool(),
            PlayMediaTool(),
            GetDevicesTool(),
        ]
