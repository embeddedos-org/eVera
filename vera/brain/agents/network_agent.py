"""Network Agent -- ping, traceroute, speed test, network info, whois."""
from __future__ import annotations
import logging, subprocess, sys
from typing import Any
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier
logger = logging.getLogger(__name__)

class PingTool(Tool):
    def __init__(self): super().__init__(name="ping",description="Ping a host",parameters={"host":{"type":"str","description":"Host to ping"},"count":{"type":"int","description":"Ping count"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        flag="-n" if sys.platform=="win32" else "-c"
        try:
            r=subprocess.run(["ping",flag,str(kw.get("count",4)),kw.get("host","8.8.8.8")],capture_output=True,text=True,timeout=30)
            return {"status":"success","output":r.stdout[:2000],"reachable":r.returncode==0}
        except Exception as e: return {"status":"error","message":str(e)}

class TracerouteTool(Tool):
    def __init__(self): super().__init__(name="traceroute",description="Trace route to host",parameters={"host":{"type":"str","description":"Target host"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        cmd="tracert" if sys.platform=="win32" else "traceroute"
        try:
            r=subprocess.run([cmd,kw.get("host","8.8.8.8")],capture_output=True,text=True,timeout=60)
            return {"status":"success","output":r.stdout[:3000]}
        except Exception as e: return {"status":"error","message":str(e)}

class SpeedTestTool(Tool):
    def __init__(self): super().__init__(name="speed_test",description="Test internet speed",parameters={})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import speedtest; st=speedtest.Speedtest(); st.get_best_server()
            return {"status":"success","download_mbps":round(st.download()/1e6,2),"upload_mbps":round(st.upload()/1e6,2),"ping_ms":round(st.results.ping,2)}
        except ImportError: return {"status":"error","message":"pip install speedtest-cli"}
        except Exception as e: return {"status":"error","message":str(e)}

class NetworkInfoTool(Tool):
    def __init__(self): super().__init__(name="network_info",description="Get network interface info",parameters={})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import psutil
            ifaces={name:[{"address":a.address,"netmask":a.netmask} for a in addrs if a.address] for name,addrs in psutil.net_if_addrs().items()}
            stats=psutil.net_io_counters()
            return {"status":"success","interfaces":ifaces,"io":{"sent_mb":round(stats.bytes_sent/1e6,2),"recv_mb":round(stats.bytes_recv/1e6,2)}}
        except ImportError: return {"status":"error","message":"pip install psutil"}
        except Exception as e: return {"status":"error","message":str(e)}

class WhoisTool(Tool):
    def __init__(self): super().__init__(name="whois_lookup",description="WHOIS lookup for domain",parameters={"domain":{"type":"str","description":"Domain"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            r=subprocess.run(["whois",kw.get("domain","")],capture_output=True,text=True,timeout=15)
            return {"status":"success","output":r.stdout[:3000]}
        except Exception as e: return {"status":"error","message":str(e)}

class NetworkAgent(BaseAgent):
    name = "network"
    description = "Ping, traceroute, speed test, network info, WHOIS lookup"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Network Agent. Ping hosts, trace routes, test speed, get network info, WHOIS lookups."
    offline_responses = {"ping":"\U0001f4e1 Pinging!","speed":"\U0001f680 Speed test!","network":"\U0001f310 Network!","whois":"\U0001f50d Looking up!"}
    def _setup_tools(self): self._tools = [PingTool(),TracerouteTool(),SpeedTestTool(),NetworkInfoTool(),WhoisTool()]
