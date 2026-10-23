"""Safely free a port: stop the container or terminate the process behind it."""

from __future__ import annotations

import os
from dataclasses import dataclass

import psutil

from . import docker_map
from .scanner import PortEntry

# Never touch these, whatever port they hold.
PROTECTED_NAMES = {
    # Windows
    "system", "system idle process", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "lsaiso.exe", "dwm.exe", "explorer.exe",
    "spoolsv.exe", "registry", "memory compression", "secure system",
    # macOS
    "launchd", "kernel_task", "windowserver", "mdnsresponder", "rapportd", "controlcenter",
    "sharingd", "airplayxpchelper", "logd", "configd", "loginwindow",
    # Linux
    "systemd", "init", "systemd-resolved", "systemd-networkd", "systemd-logind", "dbus-daemon",
    "networkmanager", "sshd", "cupsd", "avahi-daemon", "chronyd", "kthreadd",
}
PROTECTED_PIDS = {0, 1, 4}


@dataclass
class Plan:
    kind: str  # "container" | "process" | "refuse"
    target: str  # container name or pid
    description: str
    entry: PortEntry | None = None


def plan_for(entry: PortEntry) -> Plan:
    """Decide what freeing this port would do, without doing it."""
    if entry.container:
        ct = entry.container
        return Plan("container", ct.name or ct.id, f'Port {entry.port} belongs to container "{ct.name}" ({ct.image}). Stop it?', entry)
    if entry.pid is None:
        return Plan("refuse", "", f"Port {entry.port}: can't see who owns it (try running as administrator / sudo).", entry)
    reason = protected_reason(entry.pid, entry.name)
    if reason:
        return Plan("refuse", str(entry.pid), f"Port {entry.port} is held by {entry.name or 'PID ' + str(entry.pid)}: {reason}. Refusing.", entry)
    label = f"{entry.name} (PID {entry.pid})" if entry.name else f"PID {entry.pid}"
    return Plan("process", str(entry.pid), f"Port {entry.port} belongs to {label}. Stop it?", entry)


def protected_reason(pid: int, name: str = "") -> str:
    if pid in PROTECTED_PIDS:
        return "it's a core operating-system process"
    if pid == os.getpid():
        return "that's PortPilot itself"
    if (name or "").lower() in PROTECTED_NAMES:
        return "it's a system-critical process"
    return ""


def execute(plan: Plan, timeout: float = 3.0, force: bool = False) -> tuple[bool, str]:
    """Carry out a plan. Processes get a polite terminate, then kill if still alive."""
    if plan.kind == "refuse":
        return False, plan.description
    if plan.kind == "container":
        ok, msg = docker_map.stop_container(plan.target)
        port = plan.entry.port if plan.entry else ""
        return ok, f"{msg} · port {port} is free" if ok else msg
    pid = int(plan.target)
    try:
        proc = psutil.Process(pid)
        # guard against PID reuse between scan and kill
        if plan.entry and plan.entry.started and abs(proc.create_time() - plan.entry.started) > 1:
            return False, f"PID {pid} is now a different process; refresh and try again."
        if force:
            proc.kill()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
        name = plan.entry.name if plan.entry else ""
        port = plan.entry.port if plan.entry else ""
        return True, f"stopped {name or 'process'} (PID {pid}) · port {port} is free"
    except psutil.NoSuchProcess:
        return True, f"PID {pid} already exited"
    except psutil.AccessDenied:
        return False, f"Permission denied for PID {pid}. Run as administrator / with sudo."
    except psutil.TimeoutExpired:
        return False, f"PID {pid} did not exit."
