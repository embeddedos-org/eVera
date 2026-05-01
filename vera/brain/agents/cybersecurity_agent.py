"""Cyber Security Agent -- security scanning, network monitoring, threat detection."""

from __future__ import annotations

import hashlib
import logging
import socket
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class PortScanTool(Tool):
    def __init__(self):
        super().__init__(
            name="port_scan",
            description="Scan ports on a host",
            parameters={
                "host": {"type": "str", "description": "Target host"},
                "ports": {"type": "str", "description": "Port range (1-1024 or 80,443,8080)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        host, ps = kw.get("host", "localhost"), kw.get("ports", "1-1024")
        open_p = []
        try:
            plist = range(*map(int, ps.split("-"))) if "-" in ps else [int(p) for p in ps.split(",")]
            for port in plist:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    if s.connect_ex((host, port)) == 0:
                        open_p.append(port)
                    s.close()
                except:
                    pass
            return {"status": "success", "host": host, "open_ports": open_p}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PasswordStrengthTool(Tool):
    def __init__(self):
        super().__init__(
            name="password_strength",
            description="Check password strength",
            parameters={"password": {"type": "str", "description": "Password to check"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        pw = kw.get("password", "")
        s = 0
        fb = []
        if len(pw) >= 8:
            s += 1
        else:
            fb.append("Min 8 chars")
        if len(pw) >= 12:
            s += 1
        if any(c.isupper() for c in pw):
            s += 1
        else:
            fb.append("Add uppercase")
        if any(c.islower() for c in pw):
            s += 1
        if any(c.isdigit() for c in pw):
            s += 1
        else:
            fb.append("Add numbers")
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw):
            s += 1
        else:
            fb.append("Add symbols")
        return {
            "status": "success",
            "strength": ["Very Weak", "Weak", "Fair", "Good", "Strong", "Very Strong", "Excellent"][min(s, 6)],
            "score": f"{s}/6",
            "tips": fb,
        }


class HashTool(Tool):
    def __init__(self):
        super().__init__(
            name="hash_tool",
            description="Generate/verify hashes (md5/sha1/sha256/sha512)",
            parameters={
                "action": {"type": "str", "description": "hash|verify"},
                "text": {"type": "str", "description": "Text to hash"},
                "algorithm": {"type": "str", "description": "md5|sha1|sha256|sha512"},
                "expected": {"type": "str", "description": "Expected hash for verify"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        h = hashlib.new(kw.get("algorithm", "sha256"), kw.get("text", "").encode()).hexdigest()
        if kw.get("action") == "verify":
            return {"status": "success", "match": h == kw.get("expected", ""), "hash": h}
        return {"status": "success", "algorithm": kw.get("algorithm", "sha256"), "hash": h}


class SSLCheckTool(Tool):
    def __init__(self):
        super().__init__(
            name="ssl_check",
            description="Check SSL certificate of domain",
            parameters={"domain": {"type": "str", "description": "Domain"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import ssl
        from datetime import datetime

        try:
            ctx = ssl.create_default_context()
            conn = ctx.wrap_socket(socket.socket(), server_hostname=kw["domain"])
            conn.settimeout(5)
            conn.connect((kw["domain"], 443))
            cert = conn.getpeercert()
            conn.close()
            exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days = (exp - datetime.utcnow()).days
            return {
                "status": "success",
                "domain": kw["domain"],
                "expires": cert["notAfter"],
                "days_left": days,
                "valid": days > 0,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class NetworkScanTool(Tool):
    def __init__(self):
        super().__init__(
            name="network_scan",
            description="Scan local network for devices",
            parameters={"subnet": {"type": "str", "description": "Subnet (192.168.1.0/24)"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import re
        import subprocess

        try:
            r = subprocess.run(["arp", "-a"], capture_output=True, text=True)
            devices = []
            for line in r.stdout.split("\n"):
                m = re.findall(r"(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    devices.append({"ip": m[0]})
            return {"status": "success", "devices": devices, "count": len(devices)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class VulnScanTool(Tool):
    def __init__(self):
        super().__init__(
            name="vuln_check",
            description="Check Python deps for vulnerabilities",
            parameters={"requirements_file": {"type": "str", "description": "requirements.txt path"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import subprocess

        try:
            r = subprocess.run(["pip", "audit"], capture_output=True, text=True)
            return {"status": "success" if r.returncode == 0 else "warning", "output": r.stdout[:3000]}
        except:
            return {"status": "error", "message": "pip install pip-audit"}


class DNSLookupTool(Tool):
    def __init__(self):
        super().__init__(
            name="dns_lookup",
            description="DNS lookup for domain",
            parameters={
                "domain": {"type": "str", "description": "Domain"},
                "record_type": {"type": "str", "description": "A|MX|NS|TXT"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            ips = socket.getaddrinfo(kw["domain"], None, socket.AF_INET)
            return {"status": "success", "records": list(set(ip[4][0] for ip in ips))}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CyberSecurityAgent(BaseAgent):
    name = "cybersecurity"
    description = "Port scanning, password analysis, SSL checks, hashing, network scan, vulnerability detection, DNS"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Security Agent. Scan ports, check passwords, verify SSL, hash data, scan networks, check vulnerabilities, DNS lookup. Defensive security only."
    offline_responses = {
        "scan": "\U0001f50d Scanning!",
        "security": "\U0001f6e1 Security check!",
        "password": "\U0001f512 Checking!",
        "ssl": "\U0001f512 SSL check!",
    }

    def _setup_tools(self):
        self._tools = [
            PortScanTool(),
            PasswordStrengthTool(),
            HashTool(),
            SSLCheckTool(),
            NetworkScanTool(),
            VulnScanTool(),
            DNSLookupTool(),
        ]
