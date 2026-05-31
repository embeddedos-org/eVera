"""LAN Agent — discover and access computers on the local network.

Available in LAN and WWW modes. Blocked in LOCAL mode.

Capabilities:
  - Discover all devices on the LAN (ARP scan, mDNS, NetBIOS)
  - SSH into remote machines and run commands
  - List and access shared files (SMB/NFS/SFTP)
  - Query org databases on the LAN
  - Wake-on-LAN (WoL) to power on remote machines
  - Port scan a specific host
  - Ping sweep to find live hosts
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import subprocess
import sys
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class LanScanTool(Tool):
    """Discover all live hosts on the local network."""

    def __init__(self):
        super().__init__(
            name="lan_scan",
            description="Scan the local network and list all live hosts with their IP, MAC, and hostname",
            parameters={
                "subnet": {
                    "type": "str",
                    "description": "CIDR subnet to scan, e.g. 192.168.1.0/24. Leave empty to auto-detect.",
                },
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        subnet = kw.get("subnet", "")
        try:
            if not subnet:
                subnet = _detect_local_subnet()
            hosts = await _arp_scan(subnet)
            return {
                "status": "success",
                "subnet": subnet,
                "hosts_found": len(hosts),
                "hosts": hosts,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PingSweepTool(Tool):
    """Ping sweep a subnet to find live hosts."""

    def __init__(self):
        super().__init__(
            name="ping_sweep",
            description="Ping all IPs in a subnet range to find live hosts",
            parameters={
                "subnet": {"type": "str", "description": "CIDR subnet, e.g. 192.168.1.0/24"},
                "timeout": {"type": "float", "description": "Timeout per ping in seconds (default 0.5)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        subnet = kw.get("subnet", "192.168.1.0/24")
        timeout = float(kw.get("timeout", 0.5))
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            live_hosts = []
            tasks = [_async_ping(str(ip), timeout) for ip in network.hosts()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for ip, result in zip(network.hosts(), results):
                if result is True:
                    hostname = _resolve_hostname(str(ip))
                    live_hosts.append({"ip": str(ip), "hostname": hostname})
            return {
                "status": "success",
                "subnet": subnet,
                "live_hosts": len(live_hosts),
                "hosts": live_hosts,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PortScanTool(Tool):
    """Scan open ports on a specific host."""

    def __init__(self):
        super().__init__(
            name="port_scan",
            description="Scan common ports on a host to identify running services",
            parameters={
                "host": {"type": "str", "description": "IP address or hostname to scan"},
                "ports": {"type": "str", "description": "Comma-separated ports or range e.g. '22,80,443' or '1-1024'"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        host = kw.get("host", "")
        ports_str = kw.get("ports", "22,80,443,445,3389,8080,8443,3306,5432,6379,27017")
        if not host:
            return {"status": "error", "message": "host is required"}
        try:
            port_list = _parse_ports(ports_str)
            open_ports = []
            tasks = [_check_port(host, p) for p in port_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for port, is_open in zip(port_list, results):
                if is_open is True:
                    service = _port_service_name(port)
                    open_ports.append({"port": port, "service": service})
            return {
                "status": "success",
                "host": host,
                "open_ports": open_ports,
                "scanned": len(port_list),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SSHCommandTool(Tool):
    """Run a command on a remote machine via SSH."""

    def __init__(self):
        super().__init__(
            name="ssh_command",
            description="Connect to a remote machine via SSH and run a command",
            parameters={
                "host": {"type": "str", "description": "IP or hostname of the remote machine"},
                "username": {"type": "str", "description": "SSH username"},
                "command": {"type": "str", "description": "Command to run on the remote machine"},
                "password": {"type": "str", "description": "SSH password (optional if using key auth)"},
                "port": {"type": "int", "description": "SSH port (default 22)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        host = kw.get("host", "")
        username = kw.get("username", "")
        command = kw.get("command", "")
        password = kw.get("password", "")
        port = int(kw.get("port", 22))
        if not host or not username or not command:
            return {"status": "error", "message": "host, username, and command are required"}
        try:
            import paramiko  # type: ignore
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kwargs: dict[str, Any] = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 10,
            }
            if password:
                connect_kwargs["password"] = password
            client.connect(**connect_kwargs)
            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            out = stdout.read().decode("utf-8", errors="replace")[:4000]
            err = stderr.read().decode("utf-8", errors="replace")[:1000]
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            return {
                "status": "success",
                "host": host,
                "command": command,
                "exit_code": exit_code,
                "stdout": out,
                "stderr": err,
            }
        except ImportError:
            return {"status": "error", "message": "paramiko not installed. Run: pip install paramiko"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SharedFilesTool(Tool):
    """List shared files/folders on a remote machine."""

    def __init__(self):
        super().__init__(
            name="list_shared_files",
            description="List shared folders and files on a remote machine (SMB/SFTP)",
            parameters={
                "host": {"type": "str", "description": "IP or hostname"},
                "username": {"type": "str", "description": "Username"},
                "password": {"type": "str", "description": "Password"},
                "protocol": {"type": "str", "description": "Protocol: sftp or smb (default sftp)"},
                "path": {"type": "str", "description": "Remote path to list (default /)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        host = kw.get("host", "")
        username = kw.get("username", "")
        password = kw.get("password", "")
        protocol = kw.get("protocol", "sftp").lower()
        path = kw.get("path", "/")
        if not host:
            return {"status": "error", "message": "host is required"}
        try:
            if protocol == "sftp":
                return await _sftp_list(host, username, password, path)
            elif protocol == "smb":
                return await _smb_list(host, username, password, path)
            else:
                return {"status": "error", "message": f"Unknown protocol: {protocol}. Use sftp or smb"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WakeOnLanTool(Tool):
    """Send a Wake-on-LAN magic packet to power on a remote machine."""

    def __init__(self):
        super().__init__(
            name="wake_on_lan",
            description="Send a Wake-on-LAN magic packet to power on a remote computer",
            parameters={
                "mac_address": {"type": "str", "description": "MAC address of the target machine, e.g. AA:BB:CC:DD:EE:FF"},
                "broadcast": {"type": "str", "description": "Broadcast address (default 255.255.255.255)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        mac = kw.get("mac_address", "").replace(":", "").replace("-", "").upper()
        broadcast = kw.get("broadcast", "255.255.255.255")
        if len(mac) != 12:
            return {"status": "error", "message": "Invalid MAC address format"}
        try:
            magic = bytes.fromhex("FF" * 6 + mac * 16)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic, (broadcast, 9))
            sock.close()
            return {
                "status": "success",
                "message": f"Wake-on-LAN packet sent to {kw.get('mac_address')}",
                "broadcast": broadcast,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class LanQueryTool(Tool):
    """Query a database or API on the local network."""

    def __init__(self):
        super().__init__(
            name="lan_query",
            description="Query a database or REST API on the local network",
            parameters={
                "url": {"type": "str", "description": "URL of the local API or database endpoint"},
                "method": {"type": "str", "description": "HTTP method: GET or POST (default GET)"},
                "body": {"type": "str", "description": "JSON body for POST requests"},
                "headers": {"type": "str", "description": "JSON headers dict"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import json
        import urllib.request
        url = kw.get("url", "")
        method = kw.get("method", "GET").upper()
        body_str = kw.get("body", "")
        headers_str = kw.get("headers", "{}")
        if not url:
            return {"status": "error", "message": "url is required"}
        try:
            headers = json.loads(headers_str) if headers_str else {}
            headers.setdefault("Content-Type", "application/json")
            data = body_str.encode() if body_str else None
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:5000]
                return {
                    "status": "success",
                    "url": url,
                    "http_status": resp.status,
                    "response": content,
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class LANAgent(BaseAgent):
    """LAN peer discovery and access agent.

    Discovers computers on the local network, connects via SSH, lists shared
    files, queries local APIs/databases, and wakes sleeping machines.
    Only available in LAN and WWW modes.
    """

    name = "lan"
    description = (
        "Discover and access computers on your local network. "
        "Scan for devices, SSH into machines, list shared files, "
        "query org databases, and wake sleeping computers."
    )
    tier = ModelTier.SPECIALIST

    def __init__(self):
        super().__init__()

    def _setup_tools(self) -> None:
        self._tools = [
            LanScanTool(),
            PingSweepTool(),
            PortScanTool(),
            SSHCommandTool(),
            SharedFilesTool(),
            WakeOnLanTool(),
            LanQueryTool(),
        ]

    def respond_offline(self, state: Any) -> str:
        return (
            "I can help you with your local network! I can scan for devices, "
            "SSH into machines, list shared files, and query local services. "
            "What would you like to do on your LAN?"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_local_subnet() -> str:
    """Auto-detect the local subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Assume /24 subnet
        parts = local_ip.rsplit(".", 1)
        return f"{parts[0]}.0/24"
    except Exception:
        return "192.168.1.0/24"


async def _arp_scan(subnet: str) -> list[dict[str, str]]:
    """Run ARP scan using system tools."""
    hosts = []
    try:
        # Try nmap first (most accurate)
        result = await asyncio.create_subprocess_exec(
            "nmap", "-sn", "-oG", "-", subnet,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=30)
        for line in stdout.decode().splitlines():
            if "Host:" in line and "Status: Up" in line:
                parts = line.split()
                ip = parts[1] if len(parts) > 1 else ""
                hostname = parts[2].strip("()") if len(parts) > 2 else ""
                if ip:
                    hosts.append({"ip": ip, "hostname": hostname, "method": "nmap"})
        if hosts:
            return hosts
    except (FileNotFoundError, asyncio.TimeoutError):
        pass
    # Fallback: ping sweep
    network = ipaddress.ip_network(subnet, strict=False)
    tasks = [_async_ping(str(ip), 0.3) for ip in list(network.hosts())[:254]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for ip, is_live in zip(network.hosts(), results):
        if is_live is True:
            hostname = _resolve_hostname(str(ip))
            hosts.append({"ip": str(ip), "hostname": hostname, "method": "ping"})
    return hosts


async def _async_ping(ip: str, timeout: float) -> bool:
    """Async ping a single IP."""
    try:
        flag = "-n" if sys.platform == "win32" else "-c"
        wait_flag = "-w" if sys.platform == "win32" else "-W"
        proc = await asyncio.create_subprocess_exec(
            "ping", flag, "1", wait_flag, str(int(timeout * 1000)) if sys.platform == "win32" else str(int(timeout)),
            ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout + 0.5)
        return proc.returncode == 0
    except Exception:
        return False


def _resolve_hostname(ip: str) -> str:
    """Reverse DNS lookup."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def _parse_ports(ports_str: str) -> list[int]:
    """Parse port string like '22,80,443' or '1-1024'."""
    ports = []
    for part in ports_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.extend(range(int(start), int(end) + 1))
        else:
            try:
                ports.append(int(part))
            except ValueError:
                pass
    return ports[:500]  # Cap at 500 ports


async def _check_port(host: str, port: int) -> bool:
    """Check if a port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=0.5
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _port_service_name(port: int) -> str:
    """Map common ports to service names."""
    services = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
        3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
        6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
        9200: "Elasticsearch", 27017: "MongoDB",
    }
    return services.get(port, "unknown")


async def _sftp_list(host: str, username: str, password: str, path: str) -> dict[str, Any]:
    """List files via SFTP."""
    try:
        import paramiko  # type: ignore
        transport = paramiko.Transport((host, 22))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        entries = sftp.listdir_attr(path)
        files = []
        for entry in entries[:100]:
            files.append({
                "name": entry.filename,
                "size": entry.st_size,
                "is_dir": stat_is_dir(entry.st_mode),
            })
        sftp.close()
        transport.close()
        return {"status": "success", "host": host, "path": path, "files": files}
    except ImportError:
        return {"status": "error", "message": "paramiko not installed. Run: pip install paramiko"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def stat_is_dir(mode: int | None) -> bool:
    if mode is None:
        return False
    import stat
    return stat.S_ISDIR(mode)


async def _smb_list(host: str, username: str, password: str, path: str) -> dict[str, Any]:
    """List files via SMB."""
    try:
        from smb.SMBConnection import SMBConnection  # type: ignore
        conn = SMBConnection(username, password, "eVera", host, use_ntlm_v2=True)
        connected = conn.connect(host, 139, timeout=10)
        if not connected:
            return {"status": "error", "message": f"Could not connect to {host} via SMB"}
        shares = conn.listShares()
        share_list = [{"name": s.name, "type": s.type, "comments": s.comments} for s in shares]
        conn.close()
        return {"status": "success", "host": host, "shares": share_list}
    except ImportError:
        return {"status": "error", "message": "pysmb not installed. Run: pip install pysmb"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# LDAP / Active Directory Query
# ---------------------------------------------------------------------------


class LDAPQueryTool(Tool):
    """Query LDAP/Active Directory for users, groups, and org structure."""

    def __init__(self):
        super().__init__(
            name="ldap_query",
            description=(
                "Query LDAP/Active Directory: find users, list groups, get org structure, "
                "look up email addresses, phone numbers, and department info"
            ),
            parameters={
                "server": {"type": "str", "description": "LDAP server IP or hostname"},
                "base_dn": {"type": "str", "description": "Base DN e.g. 'dc=company,dc=com'"},
                "query": {"type": "str", "description": "LDAP filter e.g. '(objectClass=user)' or a name to search"},
                "username": {"type": "str", "description": "Bind username (optional for anonymous)"},
                "password": {"type": "str", "description": "Bind password"},
                "attributes": {
                    "type": "str",
                    "description": "Comma-separated attributes to return e.g. 'cn,mail,department,title'",
                },
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        server = kw.get("server", "")
        base_dn = kw.get("base_dn", "")
        query = kw.get("query", "(objectClass=user)")
        username = kw.get("username", "")
        password = kw.get("password", "")
        attrs_str = kw.get("attributes", "cn,mail,department,title,telephoneNumber,sAMAccountName")
        attrs = [a.strip() for a in attrs_str.split(",")]
        if not server or not base_dn:
            return {"status": "error", "message": "server and base_dn are required"}
        try:
            import ldap3  # type: ignore
            srv = ldap3.Server(server, get_info=ldap3.ALL)
            if username:
                conn = ldap3.Connection(srv, user=username, password=password, auto_bind=True)
            else:
                conn = ldap3.Connection(srv, auto_bind=True)
            conn.search(base_dn, query, attributes=attrs)
            results = []
            for entry in conn.entries[:50]:
                results.append({attr: str(getattr(entry, attr, "")) for attr in attrs})
            conn.unbind()
            return {"status": "success", "results": results, "count": len(results)}
        except ImportError:
            return {"status": "error", "message": "ldap3 not installed. Run: pip install ldap3"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# LAN REST API Client (Home Assistant, NAS, cameras, routers, smart home)
# ---------------------------------------------------------------------------


class LANAPICallTool(Tool):
    """Call REST APIs on local network devices."""

    def __init__(self):
        super().__init__(
            name="lan_api_call",
            description=(
                "Call REST APIs on local network devices: Home Assistant, NAS, IP cameras, "
                "routers, smart home hubs, Plex, Jellyfin, Proxmox, etc."
            ),
            parameters={
                "url": {"type": "str", "description": "Full URL e.g. 'http://192.168.1.10:8123/api/states'"},
                "method": {"type": "str", "description": "GET|POST|PUT|DELETE (default GET)"},
                "headers": {"type": "str", "description": "JSON headers e.g. '{\"Authorization\": \"Bearer token\"}'"},
                "body": {"type": "str", "description": "JSON request body for POST/PUT"},
                "timeout": {"type": "int", "description": "Timeout in seconds (default 10)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import json as _json
        import urllib.request
        url = kw.get("url", "")
        method = kw.get("method", "GET").upper()
        headers_str = kw.get("headers", "{}")
        body_str = kw.get("body", "")
        timeout = int(kw.get("timeout", 10))
        if not url:
            return {"status": "error", "message": "url is required"}
        try:
            headers = _json.loads(headers_str) if headers_str else {}
            headers.setdefault("Content-Type", "application/json")
            data = body_str.encode() if body_str else None
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:8000]
                try:
                    parsed = _json.loads(content)
                except Exception:
                    parsed = content
                return {"status": "success", "url": url, "http_status": resp.status, "response": parsed}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Printer Control
# ---------------------------------------------------------------------------


class PrinterControlTool(Tool):
    """List and control printers on the LAN."""

    def __init__(self):
        super().__init__(
            name="printer_control",
            description="List printers, print files, check print queue, cancel jobs on LAN printers",
            parameters={
                "action": {"type": "str", "description": "list|print|queue|cancel"},
                "printer": {"type": "str", "description": "Printer name (from list action)"},
                "file_path": {"type": "str", "description": "Local file path to print"},
                "job_id": {"type": "str", "description": "Job ID to cancel"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import subprocess as sp
        action = kw.get("action", "list")
        printer = kw.get("printer", "")
        file_path = kw.get("file_path", "")
        job_id = kw.get("job_id", "")
        try:
            if action == "list":
                r = sp.run(["lpstat", "-a"], capture_output=True, text=True, timeout=10)
                return {"status": "success", "printers": r.stdout or "No printers found"}
            elif action == "print":
                cmd = ["lp"]
                if printer:
                    cmd += ["-d", printer]
                cmd.append(file_path)
                r = sp.run(cmd, capture_output=True, text=True, timeout=30)
                return {"status": "success" if r.returncode == 0 else "error", "output": r.stdout, "stderr": r.stderr}
            elif action == "queue":
                cmd = ["lpq"]
                if printer:
                    cmd += ["-P", printer]
                r = sp.run(cmd, capture_output=True, text=True, timeout=10)
                return {"status": "success", "queue": r.stdout}
            elif action == "cancel":
                r = sp.run(["cancel", job_id], capture_output=True, text=True, timeout=10)
                return {"status": "success" if r.returncode == 0 else "error", "output": r.stdout}
            return {"status": "error", "message": f"Unknown action: {action}. Use list|print|queue|cancel"}
        except FileNotFoundError:
            return {"status": "error", "message": "CUPS printing system not found. Install: sudo apt install cups"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Register new tools in LANAgent
# ---------------------------------------------------------------------------

# Monkey-patch the existing LANAgent to include new tools
_original_setup = LANAgent._setup_tools


def _enhanced_setup(self) -> None:
    _original_setup(self)
    self._tools.extend([
        LDAPQueryTool(),
        LANAPICallTool(),
        PrinterControlTool(),
    ])


LANAgent._setup_tools = _enhanced_setup
