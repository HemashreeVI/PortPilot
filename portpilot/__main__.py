"""Command-line entry point.

    portpilot              live table of every listening port
    portpilot 9092         who is using port 9092?
    portpilot kill 9092    free port 9092 (asks first)
    portpilot --docker     only ports owned by Docker containers
"""

from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console
from rich.prompt import Confirm

from . import __version__, killer
from .scanner import lookup, scan
from .ui import App, print_lookup, print_table


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a port number") from None
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError("ports are between 1 and 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="portpilot",
        description="Find and free busy ports, including Docker containers.",
        epilog="examples:\n  portpilot\n  portpilot 9092\n  portpilot kill 9092\n  portpilot --docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("target", nargs="*", help="a port number, or: kill <port>")
    p.add_argument("--docker", action="store_true", help="only ports owned by Docker containers")
    p.add_argument("--udp", action="store_true", help="include UDP sockets")
    p.add_argument("--list", action="store_true", help="print the table once instead of the live view")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("-y", "--yes", action="store_true", help="kill without asking")
    p.add_argument("--force", action="store_true", help="kill immediately instead of asking the process to exit")
    p.add_argument("--version", action="version", version=f"portpilot {__version__}")
    return p


def cmd_kill(port: int, args, console: Console) -> int:
    entries = lookup(port)
    if not entries:
        console.print(f"[bold green]✔ Port {port} is already free.[/]")
        return 0
    code = 0
    for e in entries:
        plan = killer.plan_for(e)
        if plan.kind == "refuse":
            console.print(f"[bold #F5B841]🛡 {plan.description}[/]")
            code = 2
            continue
        if not args.yes and not Confirm.ask(f"[bold #F5B841]?[/] {plan.description}", default=False, console=console):
            console.print("[dim]Cancelled.[/]")
            code = 1
            continue
        ok, msg = killer.execute(plan, force=args.force)
        console.print(f"[bold green]✔ {msg}[/]" if ok else f"[bold red]✖ {msg}[/]")
        code = code or (0 if ok else 1)
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Old Windows code pages can't print ✔ or 🐳; never crash over a glyph.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):
                pass
    console = Console()
    t = args.target
    try:
        if t and t[0] == "kill":
            if len(t) != 2:
                build_parser().error("usage: portpilot kill <port>")
            return cmd_kill(_port(t[1]), args, console)
        if t:
            if len(t) != 1:
                build_parser().error("give one port, e.g. portpilot 9092")
            port = _port(t[0])
            entries = lookup(port)
            if args.json:
                print(json.dumps([e.to_dict() for e in entries], indent=2))
            else:
                print_lookup(port, entries, console)
            return 0 if entries else 1
        if args.json or args.list or not sys.stdout.isatty():
            rows = scan(include_udp=args.udp)
            if args.docker:
                rows = [e for e in rows if e.container]
            if args.json:
                print(json.dumps([e.to_dict() for e in rows], indent=2))
            else:
                print_table(rows, console)
            return 0
        App(docker_only=args.docker, include_udp=args.udp, console=console).run()
        return 0
    except argparse.ArgumentTypeError as exc:
        console.print(f"[bold red]✖ {exc}[/]")
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
