# Contributing to PortPilot

Thanks for helping! PortPilot is small on purpose, so contributions are easy to review.

## Set up

```bash
git clone https://github.com/HemashreeVI/PortPilot.git
cd PortPilot
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Where things live

| File | What it does |
|---|---|
| `portpilot/scanner.py` | finds listening sockets and the process behind each |
| `portpilot/docker_map.py` | maps published ports to containers via the `docker` CLI |
| `portpilot/killer.py` | decides what freeing a port would do, then does it safely |
| `portpilot/ui.py` | Rich table, lookup panel and the interactive TUI |
| `portpilot/hints.py` | well-known port names (5432 → PostgreSQL) |

## Good first contributions

- Add a well-known port to `hints.py` (with a test if it's surprising).
- Add a process name to the protected list in `killer.py` if PortPilot should never stop it.
- Improve platform notes in the README after trying PortPilot on your OS.

## Pull requests

1. Create a branch: `git switch -c fix/short-description`.
2. Keep the change focused and add or update a test in `tests/`.
3. Run `pytest` locally; CI runs it on Windows, macOS and Linux.
4. Add a line under **[Unreleased]** in `CHANGELOG.md`.

## Safety first

PortPilot can stop processes, so changes to `killer.py` must keep the rules: always ask (unless `-y`), never touch protected processes, terminate before kill, and re-check the PID before acting.
