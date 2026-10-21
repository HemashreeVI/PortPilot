<div align="center">

<img src="./banner.svg" alt="PortPilot — find and free busy ports, including Docker containers" width="100%"/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&size=19&duration=2600&pause=900&color=60A5FA&center=true&vCenter=true&width=700&height=40&lines=%E2%9D%8C+Error%3A+port+9092+is+already+in+use;%F0%9F%A7%AD+PortPilot%3A+it's+your+Kafka+container.;%E2%8C%A8%EF%B8%8F+Press+K+to+free+it.;%E2%9C%85+Done.+Back+to+building." alt="typing intro"/>

<p>
<img src="https://img.shields.io/badge/status-in_development-F5B841?style=for-the-badge" alt="status"/>
<img src="https://img.shields.io/badge/works_on-Windows_·_macOS_·_Linux-60A5FA?style=for-the-badge" alt="cross-platform"/>
</p>
<p>
<img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
<img src="https://img.shields.io/badge/Docker-aware-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
<img src="https://img.shields.io/badge/UI-Rich_TUI-F472B6?style=flat-square" alt="Rich"/>
<img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT"/>
</p>

**[⚡ Install](#-install)** · **[🕹️ Usage](#%EF%B8%8F-usage)** · **[🧭 How it works](#-how-it-works)** · **[🗺️ Roadmap](#%EF%B8%8F-roadmap)**

</div>

---

## 😤 The problem

You start your app and get:

```text
OSError: [Errno 98] Address already in use: ('0.0.0.0', 9092)
```

Then the usual hunt begins: `netstat -ano | findstr 9092`, copy a PID, open Task Manager, find nothing, and realise it's actually a **Docker container**, so you go and stop that too.

**PortPilot does all of that in one screen.**

## ✨ Features

<table>
<tr>
<td width="33%" align="center">🔎<br/><b>See every port</b><br/><sub>Port, PID, process name, user and uptime in one live table</sub></td>
<td width="33%" align="center">🐳<br/><b>Docker-aware</b><br/><sub>Shows <i>which container</i> owns a port, not just "com.docker.backend"</sub></td>
<td width="33%" align="center">⌨️<br/><b>One-key free</b><br/><sub>Select a row and press <kbd>K</kbd>. It stops the process or the container.</sub></td>
</tr>
<tr>
<td align="center">🎯<br/><b>Ask about one port</b><br/><sub><code>portpilot 9092</code> answers "who is on 9092?"</sub></td>
<td align="center">🛡️<br/><b>Safe by default</b><br/><sub>Asks before killing and refuses to touch system-critical processes</sub></td>
<td align="center">🖥️<br/><b>Cross-platform</b><br/><sub>PowerShell, macOS Terminal and Linux shells</sub></td>
</tr>
</table>

## 🕹️ Usage

```bash
portpilot              # live table of every listening port
portpilot 9092         # who is using port 9092?
portpilot kill 9092    # free port 9092 (asks first)
portpilot --docker     # only ports owned by Docker containers
```

**Example**

```text
PS> portpilot
PORT   PID     NAME            SOURCE
5432   1840    postgres        local
9092   7731    kafka           🐳 docker: kafka-1
8000   3022    uvicorn         local

PS> portpilot kill 9092
? Port 9092 belongs to container "kafka-1". Stop it? (y/N) y
✔ stopped container kafka-1 · port 9092 is free
```

> 🎬 *A terminal recording (GIF) goes here once the TUI is built.*

## 🧭 How it works

```mermaid
flowchart LR
    A["🔌 psutil<br/>list listening sockets"] --> B["🧩 Match port → PID → process"]
    C["🐳 Docker API<br/>published ports"] --> D["🔗 Match port → container"]
    B --> E["📋 Rich table"]
    D --> E
    E -- "press K" --> F{"Container?"}
    F -- "yes" --> G["docker stop"]
    F -- "no" --> H["terminate process"]
```

## ⚡ Install

```bash
git clone https://github.com/HemashreeVI/portpilot.git
cd portpilot
pip install -e .
portpilot
```

## 🗂️ Project structure

```
portpilot/
├── portpilot/
│   ├── __main__.py     # command-line entry point
│   ├── scanner.py      # finds listening ports and their processes
│   ├── docker_map.py   # maps ports to Docker containers
│   ├── killer.py       # safely stops a process or container
│   └── ui.py           # Rich table and key handling
├── tests/
├── pyproject.toml
└── README.md
```

## 🗺️ Roadmap

- [ ] **Step 1:** List all listening ports with PID and process name
- [ ] **Step 2:** `portpilot <port>` lookup
- [ ] **Step 3:** Map ports to Docker containers
- [ ] **Step 4:** Safe kill (process or `docker stop`) with confirmation
- [ ] **Step 5:** Live interactive TUI with one-key actions
- [ ] *Stretch:* publish to PyPI (`pip install portpilot`), common-port hints (`5432 → Postgres`)

## 🧰 Built with

<p align="center"><img src="https://skillicons.dev/icons?i=py,docker,powershell,bash,linux,windows&theme=dark" alt="tech"/></p>

---

<div align="center">

**Built by [Hemashree V I](https://hemashreevi.github.io)**, born from a real `localhost:9092` headache 🧭

<a href="https://hemashreevi.github.io"><img src="https://img.shields.io/badge/Portfolio-8B5CF6?style=flat-square&logo=googlechrome&logoColor=white" alt="Portfolio"/></a>
<a href="https://www.linkedin.com/in/hema-shree-373622289"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn"/></a>
<a href="mailto:shreejith2005@gmail.com"><img src="https://img.shields.io/badge/Email-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"/></a>

</div>
