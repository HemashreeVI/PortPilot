import socket
import subprocess
import sys
import time
from collections import namedtuple

import psutil
import pytest

from portpilot import docker_map, killer
from portpilot.__main__ import main
from portpilot.hints import hint_for
from portpilot.scanner import PortEntry, format_uptime, lookup, scan
from portpilot.ui import App, build_table, display_name

Addr = namedtuple("Addr", "ip port")
Conn = namedtuple("Conn", "fd family type laddr raddr status pid")


def tcp(port, pid, ip="0.0.0.0", status=psutil.CONN_LISTEN):
    return Conn(-1, socket.AF_INET, socket.SOCK_STREAM, Addr(ip, port), (), status, pid)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def listener():
    """A real child process listening on a free port."""
    port = free_port()
    code = f"import socket,time; s=socket.socket(); s.bind(('127.0.0.1',{port})); s.listen(); print('ok', flush=True); time.sleep(60)"
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "ok"
    yield port, proc
    proc.kill()
    proc.wait()


# ---- hints
def test_hints():
    assert hint_for(5432) == "PostgreSQL"
    assert hint_for(9092) == "Kafka"
    assert hint_for(12345) == ""


# ---- docker port parsing
@pytest.mark.parametrize("text,expected", [
    ("0.0.0.0:9092->9092/tcp, :::9092->9092/tcp", [(9092, 9092, "tcp")]),
    ("127.0.0.1:5433->5432/tcp", [(5433, 5432, "tcp")]),
    ("0.0.0.0:8000-8001->80-81/tcp", [(8000, 80, "tcp"), (8001, 81, "tcp")]),
    ("[::]:53->53/udp", [(53, 53, "udp")]),
    ("80/tcp", []),  # exposed but not published
    ("", []),
])
def test_parse_ports(text, expected):
    assert docker_map.parse_ports(text) == expected


def test_port_map_from_docker_ps():
    out = '{"ID":"abc123def4567890","Names":"kafka-1","Image":"bitnami/kafka:3.7","Ports":"0.0.0.0:9092->9092/tcp"}\n'
    runner = lambda args, timeout=5: subprocess.CompletedProcess(args, 0, out, "")
    m = docker_map.port_map(runner)
    ct = m[(9092, "tcp")]
    assert (ct.name, ct.id, ct.container_port) == ("kafka-1", "abc123def456", 9092)


def test_port_map_docker_missing():
    assert docker_map.port_map(lambda *a, **k: None) == {}
    failing = lambda args, timeout=5: subprocess.CompletedProcess(args, 1, "", "Cannot connect to the Docker daemon")
    assert docker_map.port_map(failing) == {}


# ---- scanner
def test_scan_merges_ipv4_ipv6_and_skips_non_listening():
    conns = [tcp(5432, None, "0.0.0.0"), tcp(5432, None, "::"), tcp(5000, None, status=psutil.CONN_ESTABLISHED)]
    rows = scan(connections=conns, containers={})
    assert [(r.port, r.addresses) for r in rows] == [(5432, ["0.0.0.0", "::"])]
    assert rows[0].public and rows[0].hint == "PostgreSQL"


def test_scan_attaches_container_only_to_docker_owned_ports():
    ct = docker_map.Container("abc", "kafka-1", "bitnami/kafka", 9092)
    rows = scan(connections=[tcp(9092, None)], containers={(9092, "tcp"): ct})
    assert rows[0].container == ct and rows[0].source == "docker: kafka-1"
    assert display_name(rows[0]) == "kafka"


def test_scan_adds_containers_without_host_socket():
    ct = docker_map.Container("abc", "redis", "redis:7", 6379)
    rows = scan(connections=[], containers={(6379, "tcp"): ct})
    assert rows[0].port == 6379 and rows[0].is_docker


def test_scan_finds_real_listener(listener):
    port, proc = listener
    rows = lookup(port, with_docker=False)
    assert rows and rows[0].pid == proc.pid
    assert "python" in rows[0].name.lower()


def test_scan_falls_back_when_os_denies_global_view(listener, monkeypatch):
    """macOS without sudo: psutil.net_connections raises AccessDenied."""
    port, proc = listener

    def denied(kind="inet"):
        raise psutil.AccessDenied()

    monkeypatch.setattr(psutil, "net_connections", denied)
    rows = lookup(port, with_docker=False)
    assert rows and rows[0].pid == proc.pid


def test_format_uptime():
    assert format_uptime(None) == "-"
    assert format_uptime(42) == "42s"
    assert format_uptime(125) == "2m 05s"
    assert format_uptime(3 * 3600 + 60) == "3h 01m"
    assert format_uptime(2 * 86400 + 3600) == "2d 1h"


# ---- killer safety
def test_refuses_system_and_unknown():
    assert killer.plan_for(PortEntry(port=135, proto="tcp", pid=4, name="System")).kind == "refuse"
    assert killer.plan_for(PortEntry(port=22, proto="tcp", pid=900, name="sshd")).kind == "refuse"
    assert killer.plan_for(PortEntry(port=80, proto="tcp", pid=None)).kind == "refuse"
    import os
    assert killer.plan_for(PortEntry(port=1, proto="tcp", pid=os.getpid(), name="python")).kind == "refuse"


def test_container_plan_uses_docker_stop():
    e = PortEntry(port=9092, proto="tcp", container=docker_map.Container("abc", "kafka-1", "kafka", 9092))
    plan = killer.plan_for(e)
    assert plan.kind == "container" and plan.target == "kafka-1"


def test_kill_real_process(listener):
    port, proc = listener
    (entry,) = lookup(port, with_docker=False)
    plan = killer.plan_for(entry)
    assert plan.kind == "process"
    ok, msg = killer.execute(plan)
    assert ok, msg
    proc.wait(timeout=5)
    assert lookup(port, with_docker=False) == []


# ---- CLI
def test_cli_lookup_free_port(capsys):
    assert main([str(free_port())]) == 1
    assert "is free" in capsys.readouterr().out


def test_cli_lookup_busy_json(listener, capsys):
    import json
    port, proc = listener
    assert main(["--json", str(port)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["pid"] == proc.pid


def test_cli_kill_with_yes(listener, capsys):
    port, proc = listener
    assert main(["kill", str(port), "-y"]) == 0
    assert "is free" in capsys.readouterr().out
    proc.wait(timeout=5)


def test_cli_rejects_bad_port(capsys):
    assert main(["99999"]) == 2


# ---- TUI logic
def test_app_keys():
    app = App()
    app.entries = [PortEntry(port=p, proto="tcp", pid=None) for p in (80, 443, 5432)]
    app.refresh = lambda: None
    app.handle("down")
    assert app.current().port == 443
    app.handle("up"); app.handle("up")
    assert app.current().port == 5432  # wraps
    app.handle("K")  # no pid -> refused, nothing pending
    assert app.pending is None and "can't see" in app.status.plain
    assert app.handle("q") is False


def test_table_adapts_to_width():
    rows = [PortEntry(port=5432, proto="tcp", pid=10, name="postgres", addresses=["0.0.0.0"])]
    narrow = [c.header for c in build_table(rows, width=80).columns]
    wide = [c.header for c in build_table(rows, width=140).columns]
    assert "USER" not in narrow and "SOURCE" in narrow
    assert "USER" in wide and "BIND" in wide
