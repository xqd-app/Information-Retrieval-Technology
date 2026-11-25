# 🚢 PacketVoyage

[![CI](https://github.com/europeanplaice/packetvoyage/actions/workflows/ci.yml/badge.svg)](https://github.com/europeanplaice/packetvoyage/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Model Context Protocol (MCP) Server & Agent Skill for educational network traceroute analysis, fiber-optic physics verification, and packet voyage storytelling.**
> *Zero external commercial APIs, zero bundled copyright data — pure physical laws and detective insight.*

---

## 🏛️ Architecture: The Two Pillars

PacketVoyage is built around two complementary layers designed specifically for AI-native workflows:

```text
┌────────────────────────────────────────────────────────┐
│                   AI Agent (LLM)                       │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│       🧠 Agent Skill         │ │        🛠️ MCP Server         │
│     (Knowledge / Playbook)   │ │    (Capabilities / Execution)│
├──────────────────────────────┤ ├──────────────────────────────┤
│ • Speed of Light in Fiber    │ │ • analyze_voyage_text        │
│   (~0.67c, ~10ms / 1,000km)  │ │ • voyage_investigate         │
│ • Control vs Data Plane math │ │ • run_protocol_experiment    │
│ • Disproving GeoIP illusions │ │ • research_host              │
│ • Decision Flow & Heuristics │ │ • list_known_iata_airports   │
└──────────────────────────────┘ └──────────────────────────────┘
```

1. **🛠️ MCP Server (Capabilities & Data Layer)**: FastMCP server exposing deterministic network tracing, IATA airport extraction, Team Cymru ASN resolution, and fiber-physics calculations as structured tools.
2. **🧠 Agent Skill (Knowledge & Playbook Layer)**: Progressive-disclosure skill (`SKILL.md`) teaching AI assistants how to reason through routing anomalies, explain physical fiber paths, and tell compelling stories about global Internet infrastructure.

---

## 🚀 Quickstart (MCP Server)

### Run with `uvx` (Zero-Install from GitHub)

You can launch the MCP server directly from GitHub without cloning:

```bash
uvx --from git+https://github.com/europeanplaice/packetvoyage.git packetvoyage
```

### Run Locally (Development Clone)

```bash
git clone https://github.com/europeanplaice/packetvoyage.git
cd packetvoyage
uv run packetvoyage
```

---

## ⚙️ MCP Client Configuration

### Option A: Run directly from GitHub (`uvx`)

#### Claude Desktop
Config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "packetvoyage": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/europeanplaice/packetvoyage.git",
        "packetvoyage"
      ]
    }
  }
}
```

#### Antigravity / Cursor / Windsurf / Cline
- **Antigravity**: `~/.gemini/config/mcp_config.json`
- **Cursor**: `.cursor/mcp.json`
- **Windsurf**: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "packetvoyage": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/europeanplaice/packetvoyage.git",
        "packetvoyage"
      ]
    }
  }
}
```

#### Claude Code (CLI)
```bash
claude mcp add packetvoyage -- uvx --from git+https://github.com/europeanplaice/packetvoyage.git packetvoyage
```

---

### Option B: Run from Local Clone

If you have cloned the repository locally:

```json
{
  "mcpServers": {
    "packetvoyage": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/packetvoyage",
        "run",
        "packetvoyage"
      ]
    }
  }
}
```

---

## 🛠️ Available MCP Tools

| Tool | Mode | Description |
|---|---|---|
| `analyze_voyage_text(data)` | Offline / Instant | **Primary entrypoint for pasted logs.** Parses text or JSON from terminal `traceroute`, `tracert`, Looking Glasses, or Globalping. Returns route flow, submarine cable candidates, physics checks, and mystery case files. |
| `voyage_investigate(target, data, protocol)` | Live / Local | Runs an end-to-end investigation on a target or pasted data to uncover routing anomalies (silent gaps, latency inversions, geo illusions) with fiber-optic physics verification. |
| `research_host(host, extra_resolvers, enable_asn_lookup)` | DNS / Network | Researches a target's DNS/CNAME chain *before* tracing to detect CDN/anycast fronting (which masks true origin paths). |
| `run_protocol_experiment(target)` | Live / Local | Runs parallel ICMP, TCP/443, and UDP/53 probes against a target to demonstrate firewall filtering and transport-layer routing differences. |
| `list_known_iata_airports()` | Reference | Lists reference 3-letter IATA airport codes used to infer router geographic locations from PTR hostnames. |

---

## 🧠 Agent Skill Integration

PacketVoyage includes an [Agent Skill (`skills/packetvoyage/SKILL.md`)](skills/packetvoyage/SKILL.md) that equips AI assistants with deep networking intuition:

- **Fiber-Optic Physics Verification**: Validates RTT deltas against the propagation speed of light in silica fiber glass ($v \approx 0.67c \approx 200,860\text{ km/s}$, $\approx 10\text{ms RTT per } 1,000\text{km}$).
- **GeoIP Illusion Buster**: Uses latency deltas to disprove misleading GeoIP database entries.
- **The "Sleuth" Detective Engine**: Explains why `* * *` (Asterisks) indicate router Control Plane CPU rate-limiting rather than broken links, and why latency inversions occur.
- **Oceanic & Subsea Cable Mapping**: Maps trans-oceanic transitions (e.g. `tyo` ➔ `sjc`) to known submarine cable systems (PC-1, FASTER, Unity, MAREA, etc.).

### Enabling the Skill

Copy the `skills/packetvoyage` directory into your agent's skills folder:

#### Antigravity
```bash
# Workspace (Project-level)
mkdir -p .agents/skills && cp -r skills/packetvoyage .agents/skills/

# Global (All workspaces)
mkdir -p ~/.gemini/config/skills && cp -r skills/packetvoyage ~/.gemini/config/skills/
```

#### Claude Code
```bash
# Workspace (Project-level)
mkdir -p .claude/skills && cp -r skills/packetvoyage .claude/skills/

# Personal (All projects)
mkdir -p ~/.claude/skills && cp -r skills/packetvoyage ~/.claude/skills/
```

### 💬 Example Interaction (Claude Code / Antigravity in Action)

Once the Skill and MCP server are configured, your agent seamlessly analyzes network traces, breaks down physical cable paths, and explains router telemetry mysteries:

````markdown
> **User**:
> Why are there asterisks on hop 2 in this traceroute from Tokyo to 1.1.1.1? And is it actually crossing the Pacific Ocean?
>
> ```text
> traceroute to 1.1.1.1 (1.1.1.1), 30 hops max, 60 byte packets
>  1  gateway (192.168.1.1)  0.812 ms  0.780 ms
>  2  * * *
>  3  ae-1.tokyo-hnd.bb.net (203.0.113.1)  2.100 ms  2.050 ms
>  4  xe-0-0.sjc-core.bb.net (198.51.100.25)  88.500 ms  88.450 ms
>  5  one.one.one.one (1.1.1.1)  88.700 ms  88.650 ms
> ```

> 🤖 **Claude Code (with PacketVoyage Skill + MCP)**:
>
> 🛠️ *Agent autonomously triggers `packetvoyage` skill & calls `analyze_voyage_text`...*
>
> ### 🚢 Packet Voyage Journey Report
>
> **📍 Route Summary**: `Tokyo (Haneda) [HND]` 🌊 **[JUNO / PC-1]** ➔ `San Jose [SJC]` (8,335 km)
>
> ---
>
> #### 1. 🔍 Mystery Case: The Truth Behind Hop 2 Asterisks (`* * *`)
> Hop 2 is **not dropped traffic or a broken link**. The packet reached destination `1.1.1.1` with a healthy 88.7 ms RTT.
> - **Data Plane vs. Control Plane**: Regular user traffic is forwarded in hardware ASICs (Data Plane) in nanoseconds. However, generating an `ICMP Time Exceeded` reply requires punting the probe to the router's main CPU (Control Plane).
> - **ICMP Rate-Limiting**: To protect against denial-of-service spikes, backbone routers intentionally rate-limit or silently drop diagnostic ICMP generation while continuing to forward regular payload traffic at line speed.
>
> ---
>
> #### 2. 🌊 Trans-Pacific Crossing & Fiber-Optic Physics Verification
> - **The Transition**: Hop 3 (`tokyo-hnd` in Tokyo) ➔ Hop 4 (`sjc-core` in San Jose, California).
> - **RTT Jump**: Latency jumped from **2.1 ms to 88.5 ms (+86.4 ms)**.
> - **Physical Laws of Optical Fiber**:
>   - Light in silica glass fiber propagates at $v \approx 0.67c \approx 200,860 \text{ km/s}$ (refractive index $n \approx 1.49$).
>   - **Rule of Thumb**: Every 1,000 km of fiber introduces **~10 ms of round-trip time (RTT)**.
>   - Tokyo to Silicon Valley spans ~8,300 km across the Pacific Basin. The theoretical physical lower bound is $\approx 83\text{ ms}$.
>   - The observed **+86.4 ms jump** matches the speed-of-light propagation floor through Trans-Pacific subsea cables (such as **JUNO**, **Pacific Crossing-1 (PC-1)**, or **FASTER**).
````

---

## 🧪 Testing & CI Checks

Run the local test suite and linter:

```bash
# Run full CI suite (lint, format, pytest, build check)
./scripts/check.sh

# Or run pytest directly
uv run pytest
```

---

## 📄 License

[MIT License](LICENSE)
