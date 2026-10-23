"""Rich rendering and the interactive, keyboard-driven TUI."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__, killer
from .scanner import PortEntry, format_uptime, scan

ACCENT = "#60A5FA"
DOCKER = "#2496ED"


def source_text(e: PortEntry) -> Text:
    if e.container:
        return Text.assemble(("🐳 docker: ", DOCKER), (e.container.name, f"bold {DOCKER}"))
    return Text("local", style="dim")


def display_name(e: PortEntry) -> str:
    """Docker rows show the image (kafka) rather than the proxy process (docker-proxy)."""
    if e.container:
        image = e.container.image.split("@")[0].split("/")[-1]
        return image.split(":")[0] or e.name
    return e.name or "?"


def build_table(entries: list[PortEntry], selected: int | None = None, now: float | None = None, width: int = 120) -> Table:
    """Columns adapt to the terminal: narrow screens keep PORT, PID, NAME and SOURCE readable."""
    wide = width >= 110
    show_proto = wide or any(e.proto != "tcp" for e in entries)
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {ACCENT}", expand=True, pad_edge=False)
    cols = [("PORT", dict(justify="right", style="bold", no_wrap=True, min_width=5))]
    if show_proto:
        cols.append(("PROTO", dict(style="dim", no_wrap=True, min_width=3)))
    cols += [
        ("PID", dict(justify="right", no_wrap=True, min_width=5)),
        ("NAME", dict(no_wrap=True, overflow="ellipsis", min_width=8, max_width=22, ratio=2)),
        ("SOURCE", dict(no_wrap=True, overflow="ellipsis", min_width=18, ratio=3)),
    ]
    if wide:
        cols.append(("USER", dict(style="dim", no_wrap=True, overflow="ellipsis", max_width=14, ratio=1)))
    cols.append(("UPTIME", dict(justify="right", style="dim", no_wrap=True, min_width=6)))
    if wide:
        cols.append(("BIND", dict(style="dim", no_wrap=True, overflow="ellipsis", ratio=1)))
    cols.append(("HINT", dict(style="italic #F5B841", no_wrap=True, overflow="ellipsis", ratio=1)))
    for name, kw in cols:
        t.add_column(name, **kw)
    for i, e in enumerate(entries):
        cells = {
            "PORT": str(e.port), "PROTO": e.proto, "PID": str(e.pid) if e.pid else "-",
            "NAME": display_name(e), "SOURCE": source_text(e), "USER": e.user or "-",
            "UPTIME": format_uptime(e.uptime(now)),
            "BIND": "all" if e.public else ", ".join(e.addresses) or "-", "HINT": e.hint,
        }
        t.add_row(*[cells[n] for n, _ in cols], style="bold on #1E3A5F" if i == selected else None)
    return t


def print_table(entries: list[PortEntry], console: Console | None = None) -> None:
    console = console or Console()
    if not entries:
        console.print("[dim]No listening ports found.[/] (Some may be hidden: try running as administrator / sudo.)")
        return
    console.print(build_table(entries, width=console.width))
    hidden = sum(1 for e in entries if e.pid is None and not e.container)
    if hidden:
        console.print(f"[dim]{hidden} port(s) have no visible owner. Run as administrator / sudo to see them.[/]")


def print_lookup(port: int, entries: list[PortEntry], console: Console | None = None) -> None:
    console = console or Console()
    if not entries:
        console.print(f"[bold green]✔ Port {port} is free.[/] Nothing is listening on it.")
        return
    for e in entries:
        lines = Text()
        lines.append(f"Port {e.port}/{e.proto}", style="bold")
        if e.hint:
            lines.append(f"  ({e.hint})", style="italic #F5B841")
        lines.append("\n")
        if e.container:
            ct = e.container
            lines.append("🐳 Docker container  ", style=DOCKER)
            lines.append(f"{ct.name}", style=f"bold {DOCKER}")
            lines.append(f"  image {ct.image} · id {ct.id} · container port {ct.container_port}\n", style="dim")
        lines.append("Process  ", style="dim")
        lines.append(f"{e.name or '?'}", style="bold")
        lines.append(f"  PID {e.pid if e.pid else '?'}\n")
        if e.user:
            lines.append("User     ", style="dim").append(f"{e.user}\n")
        lines.append("Uptime   ", style="dim").append(f"{format_uptime(e.uptime())}\n")
        lines.append("Bound to ", style="dim").append(", ".join(e.addresses) + ("  (reachable from other machines)" if e.public else "") + "\n")
        if e.cmdline:
            lines.append("Command  ", style="dim").append(e.cmdline[:200] + "\n")
        lines.append(f"\nFree it with: portpilot kill {e.port}", style=ACCENT)
        console.print(Panel(lines, title=f"[bold]who is on {port}?[/]", border_style=ACCENT, expand=False))


# ---------------------------------------------------------------- keyboard input

class KeyReader:
    """Read single keys without Enter on Windows (msvcrt) and POSIX (termios)."""

    def __init__(self):
        self._win = os.name == "nt"

    @contextmanager
    def raw(self):
        if self._win:
            yield self
            return
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            yield self
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def read(self, timeout: float) -> str | None:
        """Return a key name ('up', 'down', 'enter', 'esc', or a character) or None."""
        if self._win:
            import msvcrt

            end = time.time() + timeout
            while time.time() < end:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        code = msvcrt.getwch()
                        return {"H": "up", "P": "down", "I": "pgup", "Q": "pgdn", "G": "home", "O": "end"}.get(code)
                    return {"\r": "enter", "\x1b": "esc", "\x03": "ctrl-c"}.get(ch, ch)
                time.sleep(0.02)
            return None
        import select

        fd = sys.stdin.fileno()
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            return None
        ch = os.read(fd, 1).decode(errors="ignore")
        if ch == "\x1b":
            r, _, _ = select.select([fd], [], [], 0.03)
            if not r:
                return "esc"
            seq = os.read(fd, 2).decode(errors="ignore")
            return {"[A": "up", "[B": "down", "[H": "home", "[F": "end", "[5": "pgup", "[6": "pgdn"}.get(seq)
        return {"\n": "enter", "\r": "enter", "\x03": "ctrl-c"}.get(ch, ch)


# ---------------------------------------------------------------- interactive app

class App:
    """Live table: ↑/↓ select · K free port · D docker only · / filter · R refresh · Q quit."""

    REFRESH = 2.0

    def __init__(self, docker_only: bool = False, include_udp: bool = False, console: Console | None = None):
        self.console = console or Console()
        self.docker_only = docker_only
        self.include_udp = include_udp
        self.entries: list[PortEntry] = []
        self.sel = 0
        self.filter = ""
        self.typing_filter = False
        self.pending: killer.Plan | None = None
        self.status = Text("")
        self.last_scan = 0.0

    def refresh(self) -> None:
        keep = self.current()
        rows = scan(include_udp=self.include_udp)
        if self.docker_only:
            rows = [e for e in rows if e.container]
        if self.filter:
            f = self.filter.lower()
            rows = [e for e in rows if f in f"{e.port} {e.name} {e.source} {e.hint} {e.user}".lower()]
        self.entries = rows
        if keep:
            for i, e in enumerate(rows):
                if (e.port, e.proto, e.pid) == (keep.port, keep.proto, keep.pid):
                    self.sel = i
                    break
        self.sel = max(0, min(self.sel, len(rows) - 1))
        self.last_scan = time.time()

    def current(self) -> PortEntry | None:
        return self.entries[self.sel] if 0 <= self.sel < len(self.entries) else None

    def render(self):
        head = Text.assemble(
            ("🧭 PortPilot ", f"bold {ACCENT}"), (f"v{__version__}  ", "dim"),
            (f"{len(self.entries)} listening", "bold"),
            ("  · docker only" if self.docker_only else "", DOCKER),
            (f"  · filter: {self.filter}" if self.filter else "", "#F5B841"),
        )
        table = build_table(self.entries, self.sel, width=self.console.width) if self.entries else Text("\n  No listening ports match.\n", style="dim")
        if self.pending:
            footer = Text.assemble(("? ", "bold #F5B841"), (self.pending.description, "bold"), ("  (y/N)", "dim"))
        elif self.typing_filter:
            footer = Text.assemble(("/ ", "bold #F5B841"), (self.filter, "bold"), ("▌", ACCENT), ("   Enter to apply · Esc to clear", "dim"))
        else:
            footer = Text.assemble(
                ("↑↓", "bold"), (" select  ", "dim"), ("K", "bold"), (" free port  ", "dim"),
                ("D", "bold"), (" docker only  ", "dim"), ("/", "bold"), (" filter  ", "dim"),
                ("R", "bold"), (" refresh  ", "dim"), ("Q", "bold"), (" quit", "dim"),
            )
        return Group(head, table, self.status, footer)

    def handle(self, key: str) -> bool:
        """Process one key. Returns False to quit."""
        if self.pending:
            if key in ("y", "Y"):
                ok, msg = killer.execute(self.pending)
                self.status = Text(("✔ " if ok else "✖ ") + msg, style="bold green" if ok else "bold red")
                self.pending = None
                self.refresh()
            else:
                self.pending = None
                self.status = Text("Cancelled.", style="dim")
            return True
        if self.typing_filter:
            if key == "enter":
                self.typing_filter = False
                self.refresh()
            elif key == "esc":
                self.typing_filter, self.filter = False, ""
                self.refresh()
            elif key in ("\x7f", "\b"):
                self.filter = self.filter[:-1]
            elif key and len(key) == 1 and key.isprintable():
                self.filter += key
            return True
        if key in ("q", "Q", "esc", "ctrl-c"):
            return False
        n = len(self.entries)
        if key == "up" and n:
            self.sel = (self.sel - 1) % n
        elif key == "down" and n:
            self.sel = (self.sel + 1) % n
        elif key == "home":
            self.sel = 0
        elif key == "end":
            self.sel = max(0, n - 1)
        elif key == "pgup":
            self.sel = max(0, self.sel - 10)
        elif key == "pgdn":
            self.sel = min(max(0, n - 1), self.sel + 10)
        elif key in ("k", "K"):
            e = self.current()
            if e:
                plan = killer.plan_for(e)
                if plan.kind == "refuse":
                    self.status = Text("🛡 " + plan.description, style="bold #F5B841")
                else:
                    self.pending = plan
        elif key in ("d", "D"):
            self.docker_only = not self.docker_only
            self.refresh()
        elif key in ("r", "R"):
            self.refresh()
            self.status = Text("Refreshed.", style="dim")
        elif key == "/":
            self.typing_filter = True
        return True

    def run(self) -> None:
        if not sys.stdin.isatty():
            print_table(scan(include_udp=self.include_udp), self.console)
            return
        reader = KeyReader()
        self.refresh()
        with reader.raw(), Live(self.render(), console=self.console, screen=True, auto_refresh=False) as live:
            while True:
                key = reader.read(0.25)
                if key is not None and not self.handle(key):
                    break
                if not self.pending and not self.typing_filter and time.time() - self.last_scan > self.REFRESH:
                    self.refresh()
                live.update(self.render(), refresh=True)
