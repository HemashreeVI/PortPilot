"""Map published host ports to the Docker containers that own them.

Uses the `docker` CLI (no SDK dependency), so it works with Docker Desktop on
Windows/macOS and with dockerd on Linux. If Docker isn't installed or running,
every function degrades to "no containers" instead of failing.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass

# Process names that front Docker-published ports on each platform.
DOCKER_PROXY_NAMES = {
    "docker-proxy", "com.docker.backend", "com.docker.vpnkit", "vpnkit", "vpnkit-bridge",
    "wslrelay", "wslrelay.exe", "com.docker.backend.exe", "docker desktop.exe",
    "dockerd", "rootlesskit", "slirp4netns", "gvproxy", "colima", "limactl",
}

_PORT_RE = re.compile(r"(?:(?P<ip>[\d.]+|\[?[0-9a-fA-F:]*\]?):)?(?P<host>\d+)(?:-(?P<host_end>\d+))?->(?P<cport>\d+)(?:-\d+)?/(?P<proto>tcp|udp|sctp)")


@dataclass(frozen=True)
class Container:
    id: str
    name: str
    image: str
    container_port: int
    proto: str = "tcp"


def is_docker_proxy(process_name: str | None) -> bool:
    return bool(process_name) and process_name.lower() in DOCKER_PROXY_NAMES


def parse_ports(ports: str) -> list[tuple[int, int, str]]:
    """Parse `docker ps` Ports text into (host_port, container_port, proto) tuples.

    >>> parse_ports("0.0.0.0:9092->9092/tcp, :::9092->9092/tcp")
    [(9092, 9092, 'tcp')]
    """
    out: list[tuple[int, int, str]] = []
    for m in _PORT_RE.finditer(ports or ""):
        start = int(m["host"])
        end = int(m["host_end"] or start)
        cport = int(m["cport"])
        for i, host in enumerate(range(start, end + 1)):
            item = (host, cport + i, m["proto"])
            if item not in out:
                out.append(item)
    return out


def docker_available() -> bool:
    return shutil.which("docker") is not None


def _run_docker(args: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess | None:
    if not docker_available():
        return None
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def port_map(runner=_run_docker) -> dict[tuple[int, str], Container]:
    """Return {(host_port, proto): Container} for every running container."""
    res = runner(["ps", "--no-trunc", "--format", "{{json .}}"])
    if res is None or res.returncode != 0:
        return {}
    mapping: dict[tuple[int, str], Container] = {}
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for host, cport, proto in parse_ports(row.get("Ports", "")):
            mapping[(host, proto)] = Container(
                id=str(row.get("ID", ""))[:12],
                name=str(row.get("Names", "")).split(",")[0],
                image=str(row.get("Image", "")),
                container_port=cport,
                proto=proto,
            )
    return mapping


def stop_container(name_or_id: str, runner=_run_docker, timeout: int = 10) -> tuple[bool, str]:
    """`docker stop` a container. Returns (ok, message)."""
    res = runner(["stop", "-t", str(timeout), name_or_id], timeout=timeout + 15)
    if res is None:
        return False, "Docker CLI not available"
    if res.returncode != 0:
        return False, (res.stderr or res.stdout).strip() or "docker stop failed"
    return True, f"stopped container {name_or_id}"
