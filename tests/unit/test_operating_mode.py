"""Tests for the three-mode operating system."""
import pytest
from vera.operating_mode import OperatingMode, ModeManager, MODE_DESCRIPTIONS


def make_manager(mode: str) -> ModeManager:
    """Create a fresh ModeManager (bypassing singleton) for testing."""
    mgr = object.__new__(ModeManager)
    mgr._initialized = True
    mgr._mode = OperatingMode(mode)
    return mgr


def test_mode_enum_values():
    assert OperatingMode.LOCAL.value == "local"
    assert OperatingMode.LAN.value == "lan"
    assert OperatingMode.WWW.value == "www"


def test_mode_descriptions_all_modes_present():
    for mode in OperatingMode:
        assert mode in MODE_DESCRIPTIONS, f"Missing description for {mode}"


def test_mode_manager_default():
    mgr = ModeManager()
    assert mgr.mode in (OperatingMode.LOCAL, OperatingMode.LAN, OperatingMode.WWW)


def test_mode_manager_set_local():
    mgr = make_manager("local")
    assert mgr.mode == OperatingMode.LOCAL


def test_mode_manager_set_lan():
    mgr = make_manager("lan")
    assert mgr.mode == OperatingMode.LAN


def test_mode_manager_set_www():
    mgr = make_manager("www")
    assert mgr.mode == OperatingMode.WWW


def test_local_mode_blocks_internet_agents():
    mgr = make_manager("local")
    assert mgr.is_agent_available("researcher") is False


def test_local_mode_blocks_browser_agent():
    mgr = make_manager("local")
    assert mgr.is_agent_available("browser") is False


def test_local_mode_allows_computer_use():
    mgr = make_manager("local")
    assert mgr.is_agent_available("computer_use") is True


def test_local_mode_allows_coder():
    mgr = make_manager("local")
    assert mgr.is_agent_available("coder") is True


def test_local_mode_allows_writer():
    mgr = make_manager("local")
    assert mgr.is_agent_available("writer") is True


def test_local_mode_no_internet():
    mgr = make_manager("local")
    assert mgr.is_internet_available() is False


def test_local_mode_no_lan():
    mgr = make_manager("local")
    assert mgr.is_lan_available() is False


def test_lan_mode_allows_devops():
    mgr = make_manager("lan")
    assert mgr.is_agent_available("devops") is True


def test_lan_mode_allows_network():
    mgr = make_manager("lan")
    assert mgr.is_agent_available("network") is True


def test_lan_mode_blocks_researcher():
    mgr = make_manager("lan")
    assert mgr.is_agent_available("researcher") is False


def test_lan_mode_has_lan_access():
    mgr = make_manager("lan")
    assert mgr.is_lan_available() is True


def test_lan_mode_no_internet():
    mgr = make_manager("lan")
    assert mgr.is_internet_available() is False


def test_www_mode_allows_all_agents():
    mgr = make_manager("www")
    for agent in ("computer_use", "researcher", "finance", "browser", "devops", "network"):
        assert mgr.is_agent_available(agent) is True, f"Agent {agent} blocked in WWW mode"


def test_www_mode_has_internet():
    mgr = make_manager("www")
    assert mgr.is_internet_available() is True


def test_www_mode_has_lan():
    mgr = make_manager("www")
    assert mgr.is_lan_available() is True


def test_get_status_returns_dict():
    mgr = make_manager("local")
    status = mgr.get_status()
    assert isinstance(status, dict)
    assert status["mode"] == "local"
    assert "description" in status
    assert "internet" in status
    assert "lan_access" in status


def test_get_offline_message_local():
    mgr = make_manager("local")
    msg = mgr.get_offline_message("researcher")
    assert "LOCAL" in msg
    assert "internet" in msg.lower()


def test_get_offline_message_lan():
    mgr = make_manager("lan")
    msg = mgr.get_offline_message("researcher")
    assert "LAN" in msg or "internet" in msg.lower()


def test_mode_change_at_runtime():
    mgr = make_manager("local")
    assert mgr.mode == OperatingMode.LOCAL
    mgr.set_mode(OperatingMode.WWW)
    assert mgr.mode == OperatingMode.WWW
    mgr.set_mode("lan")
    assert mgr.mode == OperatingMode.LAN


def test_invalid_mode_raises():
    mgr = make_manager("local")
    with pytest.raises(ValueError):
        mgr.set_mode("invalid_mode")


def test_www_agents_blocked_is_empty():
    info = MODE_DESCRIPTIONS[OperatingMode.WWW]
    assert info["agents_blocked"] == []


def test_local_agents_available_list():
    info = MODE_DESCRIPTIONS[OperatingMode.LOCAL]
    assert isinstance(info["agents_available"], list)
    assert len(info["agents_available"]) > 0


def test_www_agents_available_is_none():
    """WWW mode uses None to mean 'all agents allowed'."""
    info = MODE_DESCRIPTIONS[OperatingMode.WWW]
    assert info["agents_available"] is None
