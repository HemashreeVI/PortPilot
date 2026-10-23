# Changelog

All notable changes to PortPilot are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Install straight from GitHub: `pip install git+https://github.com/HemashreeVI/PortPilot.git`.

### Fixed
- Website links now use the case-sensitive GitHub Pages path `/PortPilot/`.

## [0.1.0] - 2026-10-23

### Added
- Live table of every listening port with PID, process, user, uptime, bind address and a common-port hint.
- Docker awareness: published ports are traced to the container that owns them instead of `docker-proxy` / `com.docker.backend`.
- `portpilot <port>` lookup with the full command line and container image.
- `portpilot kill <port>` with confirmation; containers are stopped with `docker stop`, processes are terminated politely and only force-killed after 3 s.
- Safety rules: core OS processes (PID 0/1/4, `System`, `svchost.exe`, `launchd`, `systemd`, `sshd`, …) and PortPilot itself are never touched; PID-reuse guard before killing.
- Interactive TUI: ↑/↓ select, `K` free port, `D` Docker only, `/` filter, `R` refresh, `Q` quit (Windows and POSIX key input).
- `--json`, `--list`, `--udp`, `--docker`, `-y`, `--force`; exit code 0 when a port is busy and 1 when it is free.
- Falls back to per-process scanning when the OS denies the global socket table (macOS without sudo).
- Landing page, PyPI publishing workflow (`portpilot-cli`) and CI on Windows, macOS and Linux.

[Unreleased]: https://github.com/HemashreeVI/PortPilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/HemashreeVI/PortPilot/commits/main
