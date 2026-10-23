"""Find listening ports and the processes (or containers) behind them."""

from __future__ import annotations

import socket
import time
from collections import namedtuple
from dataclasses import dataclass, field

import psutil

from . import docker_map
from .hints import hint_for


@dataclass
class PortEntry:
    port: int
    proto: str  # "tcp" | "udp"
    addresses: list[str] = field(default_factory=list)
    pid: int | None = None
    name: str = ""
    user: str = ""
    started: float | None = None  # epoch seconds
    cmdline: str = ""
    container: docker_map.Container | None = None

    @property
    def hint(self) -> str:
        return hint_for(self.port)

    @property
    def is_docker(self) -> bool:
        return self.container is not None

    @property
    def source(self) -> str:
        return f"docker: {self.container.name}" if self.container else "local"

    @property
    def public(self) -> bool:
        """True when bound to all interfaces (reachable from other machines)."""
        return any(a in ("0.0.0.0", "::", "*") for a in self.addresses)

    def uptime(self, now: float | None = None) -> float | None:
        if self.started is None:
            return None
        return max(0.0, (now or time.time()) - self.started)

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "proto": self.proto,
            "addresses": self.addresses,
            "pid": self.pid,
            "name": self.name,
            "user": self.user,
            "uptime_seconds": round(self.uptime()) if self.started else None,
            "cmdline": self.cmdline,
            "hint": self.hint,
            "container": None if not self.container else {
                "id": self.container.id,
                "name": self.container.name,
                "image": self.container.image,
                "container_port": self.container.container_port,
            },
        }


def _all_connections(kind: str):
    """psutil.net_connections, falling back to per-process scans when the OS denies
    the global view (macOS without sudo)."""
    try:
        return psutil.net_connections(kind=kind)
    except (psutil.AccessDenied, PermissionError):
        conns = []
        for proc in psutil.process_iter(["pid"]):
            try:
                getter = getattr(proc, "net_connections", None) or proc.connections
                conns.extend(_with_pid(c, proc.pid) for c in getter(kind=kind))
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
        return conns


Conn = namedtuple("Conn", "fd family type laddr raddr status pid")


def _with_pid(conn, pid):
    """Per-process connection tuples have no pid field; add one."""
    return Conn(conn.fd, conn.family, conn.type, conn.laddr, conn.raddr, conn.status, pid)


def _describe(pid: int | None) -> tuple[str, str, float | None, str]:
    if not pid:
        return ("", "", None, "")
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            name = p.name()
            try:
                user = p.username()
            except (psutil.AccessDenied, KeyError):
                user = ""
            try:
                started = p.create_time()
            except psutil.AccessDenied:
                started = None
            try:
                cmd = " ".join(p.cmdline())
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmd = ""
        return (name, user, started, cmd)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ("", "", None, "")


def scan(include_udp: bool = False, with_docker: bool = True, connections=None, containers=None) -> list[PortEntry]:
    """Return every listening port, one row per (port, proto, pid), sorted by port.

    `connections` and `containers` can be injected for testing.
    """
    if connections is None:
        connections = list(_all_connections("tcp"))
        if include_udp:
            connections += list(_all_connections("udp"))
    if containers is None:
        containers = docker_map.port_map() if with_docker else {}

    rows: dict[tuple[int, str, int | None], PortEntry] = {}
    for c in connections:
        is_tcp = c.type == socket.SOCK_STREAM
        if is_tcp and c.status != psutil.CONN_LISTEN:
            continue
        if not is_tcp and (c.raddr or not c.laddr):  # UDP: only bound, unconnected sockets
            continue
        if not c.laddr:
            continue
        proto = "tcp" if is_tcp else "udp"
        key = (c.laddr.port, proto, c.pid)
        entry = rows.get(key)
        if entry is None:
            entry = rows[key] = PortEntry(port=c.laddr.port, proto=proto, pid=c.pid)
        if c.laddr.ip not in entry.addresses:
            entry.addresses.append(c.laddr.ip)

    for entry in rows.values():
        entry.name, entry.user, entry.started, entry.cmdline = _describe(entry.pid)
        entry.container = containers.get((entry.port, entry.proto))
        # A container port held by a non-Docker process is a coincidence; only keep it
        # when the owner is unknown (no permission) or a known Docker proxy.
        if entry.container and entry.name and not docker_map.is_docker_proxy(entry.name):
            entry.container = None

    # Containers whose published port isn't visible as a host socket (e.g. Docker Desktop VM)
    seen = {(e.port, e.proto) for e in rows.values()}
    extra = [
        PortEntry(port=port, proto=proto, addresses=["0.0.0.0"], name="docker", container=ct)
        for (port, proto), ct in containers.items()
        if (port, proto) not in seen and (include_udp or proto == "tcp")
    ]
    return sorted([*rows.values(), *extra], key=lambda e: (e.port, e.proto, e.pid or 0))


def lookup(port: int, entries: list[PortEntry] | None = None, **kw) -> list[PortEntry]:
    """Everything listening on one port."""
    entries = entries if entries is not None else scan(include_udp=True, **kw)
    return [e for e in entries if e.port == port]


def format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m:02d}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"
