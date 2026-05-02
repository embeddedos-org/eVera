"""Three-layer network zone access control for eVera.

Classifies every incoming connection into one of three zones based on source IP:
  - LOCAL:  Loopback (127.0.0.1, ::1) — the machine running eVera
  - LAN:    Private network (10.x, 172.16-31.x, 192.168.x, link-local)
  - WWW:    Everything else — public internet

Each zone has configurable access policies:
  - LOCAL:  No auth required (trusted — it's your own system)
  - LAN:    API key required (trusted network, but verify identity)
  - WWW:    API key + rate limiting (untrusted, full security)
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Any

from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class NetworkZone(str, Enum):
    """Network access zones, ordered from most trusted to least."""

    LOCAL = "local"
    LAN = "lan"
    WWW = "www"


# --- IP Classification ---

# Private/reserved IPv4 networks (RFC 1918 + loopback + link-local)
_LOOPBACK_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
]
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
]


def classify_ip(ip_str: str) -> NetworkZone:
    """Classify an IP address into a network zone.

    @param ip_str: IP address string (v4 or v6).
    @return NetworkZone enum value.
    """
    stripped = ip_str.strip()

    # TestClient and other non-IP hostnames from test frameworks → LOCAL
    if stripped in ("testclient", "localhost"):
        return NetworkZone.LOCAL

    try:
        addr = ipaddress.ip_address(stripped)
    except ValueError:
        logger.warning("Cannot parse IP '%s', treating as WWW", ip_str)
        return NetworkZone.WWW

    # IPv6 loopback
    if addr == ipaddress.ip_address("::1"):
        return NetworkZone.LOCAL

    # IPv4-mapped IPv6 (e.g., ::ffff:127.0.0.1)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    if isinstance(addr, ipaddress.IPv4Address):
        for net in _LOOPBACK_NETS:
            if addr in net:
                return NetworkZone.LOCAL
        for net in _PRIVATE_NETS:
            if addr in net:
                return NetworkZone.LAN

    # IPv6 private ranges
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.is_link_local or addr.is_site_local or addr.is_private:
            return NetworkZone.LAN

    return NetworkZone.WWW


def get_client_ip(request: Request | WebSocket) -> str:
    """Extract the real client IP, respecting reverse proxy headers.

    Checks X-Forwarded-For and X-Real-IP headers first (for proxy setups),
    then falls back to the direct connection IP.

    @param request: FastAPI Request or WebSocket.
    @return Client IP as string.
    """
    # X-Forwarded-For: client, proxy1, proxy2 → take first (original client)
    forwarded = None
    if hasattr(request, "headers"):
        forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = None
    if hasattr(request, "headers"):
        real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Direct connection
    if hasattr(request, "client") and request.client:
        return request.client.host

    return "127.0.0.1"  # Fallback for testing


def classify_request(request: Request | WebSocket) -> NetworkZone:
    """Classify a request into its network zone.

    @param request: FastAPI Request or WebSocket.
    @return NetworkZone for this connection.
    """
    ip = get_client_ip(request)
    return classify_ip(ip)


# --- Rate Limiter ---


class ZoneRateLimiter:
    """Simple sliding-window rate limiter per IP.

    Only applied to WWW zone. LOCAL and LAN are not rate-limited.
    """

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.rpm = requests_per_minute
        self.burst = burst
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        """Check if a request from this IP is within rate limits.

        @param ip: Client IP address.
        @return True if allowed, False if rate-limited.
        """
        now = time.monotonic()
        window = self._windows[ip]

        # Purge entries older than 60 seconds
        cutoff = now - 60
        self._windows[ip] = [t for t in window if t > cutoff]
        window = self._windows[ip]

        if len(window) >= self.rpm:
            return False

        # Burst check: no more than `burst` requests in 1 second
        one_sec_ago = now - 1
        recent = sum(1 for t in window if t > one_sec_ago)
        if recent >= self.burst:
            return False

        window.append(now)
        return True

    def cleanup(self):
        """Remove stale entries (call periodically)."""
        now = time.monotonic()
        cutoff = now - 120
        stale = [ip for ip, times in self._windows.items() if all(t < cutoff for t in times)]
        for ip in stale:
            del self._windows[ip]


# Global rate limiter instance
rate_limiter = ZoneRateLimiter()


# --- Zone Access Policy ---


class ZonePolicy:
    """Defines access requirements for each network zone."""

    def __init__(
        self,
        zone: NetworkZone,
        auth_required: bool = False,
        rate_limited: bool = False,
        allowed_paths: list[str] | None = None,
        blocked_paths: list[str] | None = None,
    ):
        self.zone = zone
        self.auth_required = auth_required
        self.rate_limited = rate_limited
        self.allowed_paths = allowed_paths  # None = all allowed
        self.blocked_paths = blocked_paths or []

    def is_path_allowed(self, path: str) -> bool:
        """Check if a request path is allowed in this zone."""
        for blocked in self.blocked_paths:
            if path.startswith(blocked):
                return False
        if self.allowed_paths is not None:
            return any(path.startswith(p) for p in self.allowed_paths)
        return True


# Default policies per zone
DEFAULT_POLICIES: dict[NetworkZone, ZonePolicy] = {
    NetworkZone.LOCAL: ZonePolicy(
        zone=NetworkZone.LOCAL,
        auth_required=False,
        rate_limited=False,
        # LOCAL can access everything — it's your own machine
    ),
    NetworkZone.LAN: ZonePolicy(
        zone=NetworkZone.LAN,
        auth_required=True,
        rate_limited=False,
        # LAN can access everything but admin endpoints require auth
        blocked_paths=["/admin/"],
    ),
    NetworkZone.WWW: ZonePolicy(
        zone=NetworkZone.WWW,
        auth_required=True,
        rate_limited=True,
        # WWW can access all services but with auth + rate limiting
        # Admin and code endpoints blocked for internet clients
        blocked_paths=["/admin/", "/api/code/"],
    ),
}

# Paths that never require auth regardless of zone
PUBLIC_PATHS = frozenset({"/", "/health", "/metrics", "/alerts", "/network/zones"})
PUBLIC_PREFIXES = ("/static/",)


def is_public_path(path: str) -> bool:
    """Check if a path is publicly accessible without auth."""
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


# --- Middleware Helpers ---


def build_zone_headers(zone: NetworkZone, ip: str) -> dict[str, str]:
    """Build response headers that indicate the detected zone.

    @param zone: Detected network zone.
    @param ip: Client IP.
    @return Headers dict to add to response.
    """
    return {
        "X-Vera-Zone": zone.value,
        "X-Vera-Zone-Auth": "required" if DEFAULT_POLICIES[zone].auth_required else "none",
    }


async def check_zone_access(
    request: Request,
    api_key: str,
    zone_overrides: dict[NetworkZone, ZonePolicy] | None = None,
) -> JSONResponse | None:
    """Check if a request is allowed based on its network zone.

    @param request: The incoming request.
    @param api_key: The configured API key (empty = no auth).
    @param zone_overrides: Optional per-zone policy overrides.
    @return JSONResponse with error if denied, None if allowed.
    """
    zone = classify_request(request)
    ip = get_client_ip(request)
    path = request.url.path

    policies = zone_overrides or DEFAULT_POLICIES
    policy = policies.get(zone, DEFAULT_POLICIES[NetworkZone.WWW])

    # Store zone on request state for downstream use
    request.state.network_zone = zone
    request.state.client_ip = ip

    # Check if path is allowed in this zone
    if not policy.is_path_allowed(path):
        logger.warning(
            "Zone %s (IP: %s) blocked from path %s", zone.value, ip, path
        )
        return JSONResponse(
            status_code=403,
            content={
                "detail": f"Access denied: path '{path}' is not available from {zone.value} zone",
                "zone": zone.value,
            },
            headers=build_zone_headers(zone, ip),
        )

    # Check rate limiting (WWW zone only by default)
    if policy.rate_limited:
        if not rate_limiter.is_allowed(ip):
            logger.warning("Rate limit exceeded for %s (zone: %s)", ip, zone.value)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "zone": zone.value,
                },
                headers={
                    **build_zone_headers(zone, ip),
                    "Retry-After": "60",
                },
            )

    # Check auth (skip for public paths and LOCAL zone)
    if policy.auth_required and api_key and not is_public_path(path):
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {api_key}":
            logger.info(
                "Auth failed for %s from zone %s (IP: %s)", path, zone.value, ip
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required for this zone",
                    "zone": zone.value,
                    "auth_type": "bearer",
                },
                headers=build_zone_headers(zone, ip),
            )

    return None  # Access granted


async def check_ws_zone_access(
    websocket: WebSocket,
    api_key: str,
) -> bool:
    """Check WebSocket access based on network zone.

    @param websocket: The WebSocket connection.
    @param api_key: The configured API key.
    @return True if access is allowed, False if denied (WebSocket will be closed).
    """
    zone = classify_request(websocket)
    ip = get_client_ip(websocket)
    policy = DEFAULT_POLICIES.get(zone, DEFAULT_POLICIES[NetworkZone.WWW])

    # Rate limit check for WWW
    if policy.rate_limited and not rate_limiter.is_allowed(ip):
        await websocket.close(code=4029, reason="Rate limit exceeded")
        return False

    # Auth check (skip for LOCAL)
    if policy.auth_required and api_key:
        ws_api_key = websocket.query_params.get("api_key", "")
        if ws_api_key != api_key:
            await websocket.close(
                code=4001,
                reason=f"Authentication required for {zone.value} zone",
            )
            return False

    return True


def get_zone_status() -> dict[str, Any]:
    """Get the current zone configuration status for the /network/zones endpoint."""
    return {
        "zones": {
            zone.value: {
                "auth_required": policy.auth_required,
                "rate_limited": policy.rate_limited,
                "blocked_paths": policy.blocked_paths,
                "description": {
                    NetworkZone.LOCAL: "Loopback connections (127.0.0.1, ::1) — no auth needed",
                    NetworkZone.LAN: "Private network (10.x, 172.16-31.x, 192.168.x) — API key required",
                    NetworkZone.WWW: "Public internet — API key + rate limiting",
                }[zone],
            }
            for zone, policy in DEFAULT_POLICIES.items()
        },
        "public_paths": list(PUBLIC_PATHS),
        "rate_limit": {
            "requests_per_minute": rate_limiter.rpm,
            "burst_per_second": rate_limiter.burst,
        },
    }
