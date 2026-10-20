# Blueprint: Building and Debugging Connectivity-Dependent Autonomous Vehicles

From the first design decision to a fleet you can debug when it's 300 km away on a weak LTE signal.

This applies to any autonomous Linux/Python vehicle that depends on a network link: drones that live in a base station (drone-in-a-box), ground rovers, inspection robots, uncrewed boats and underwater vehicles, agricultural machines. Where something applies to only one kind of vehicle, it says so.

---

## 0. The one rule everything follows from

> **The vehicle must be safe and useful with zero connectivity. Connectivity adds visibility and control. It is never a dependency for safety.**

Everything below falls out of that rule:

| If the link is…  | The vehicle should…                                                        |
|------------------|----------------------------------------------------------------------------|
| Good             | Stream live state, upload data, accept commands, take OTA updates           |
| Degraded         | Send only heartbeats and events; queue everything else                      |
| Lost (seconds)   | Continue the current safe action; keep logging                              |
| Lost (minutes)   | Run its pre-agreed lost-link behavior (return home / hold / return to base station / stop)  |
| Lost (days)      | Stay safe, keep its black box, recover itself, and backfill when it returns |

"Ideal state" for one of these systems therefore means: **every vehicle can always answer "am I healthy, and why not?" by itself, records the answer locally, and gets it to a human as soon as any link allows.**

---

## 1. End-to-end architecture

```
 ┌───────────────────────────── VEHICLE ─────────────────────────────┐
 │                                                                   │
 │  ┌─────────────┐  MAVLink/UART  ┌──────────────────────────────┐  │
 │  │ Flight /    │◄──────────────►│ Companion computer (Linux)   │  │
 │  │ motion ctrl │                │  ├ mission / autonomy (Py)   │  │
 │  │ (PX4/ArduP. │                │  ├ perception / payloads     │  │
 │  │  RTOS, MCU) │                │  ├ HEALTH AGENT  ◄── this repo│ │
 │  └──────┬──────┘                │  ├ black-box spool + logs    │  │
 │         │ independent           │  ├ OTA client (A/B rootfs)   │  │
 │  ┌──────▼──────┐                │  └ remote-access client      │  │
 │  │ Safety sys  │                └───────┬──────────────────────┘  │
 │  │ (parachute/ │   HW watchdog ─────────┘                         │
 │  │  FTS, e-stop)│                                                  │
 │  └─────────────┘                                                  │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │ Wi-Fi / Ethernet at the base station
 ┌───────────────── BASE STATION / EDGE GATEWAY ─────────────────────┐
 │  base station controller (lid/doors, charger, HVAC, weather)      │
 │  edge computer: station agent, data cache, local ops UI           │
 │  multi-link router: LTE A + LTE B (2 carriers) / 5G / satellite   │
 │  out-of-band: cellular power relay / BMC / serial console         │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │ OUTBOUND ONLY, mTLS / WireGuard
 ┌──────────────────────────── CLOUD ────────────────────────────────┐
 │  ingest (HTTPS/MQTT) ─► time-series + event store ─► rules/alerts  │
 │  fleet registry · config service · OTA server (staged rollouts)   │
 │  remote-access broker (audited, just-in-time) · bundle storage    │
 │  ops dashboard ◄── this repo's console · analytics platform     │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │
                 NOC operators · field engineers · on-call
```

### The division between layers

| Layer | Owns | Must keep working when… |
|---|---|---|
| Flight/motion controller | Stabilization, failsafes, geofence | The companion computer crashes |
| Safety system | Parachute/FTS/e-stop | Everything else has failed |
| Companion computer | Autonomy, payloads, health, logging | The network is down |
| Base station / edge | Charging, shelter, weather gating, local cache, **multi-link** | The cloud is down |
| Cloud | Fleet view, history, OTA, alerting, humans | A single site is offline |

An operations or analytics platform (mission planning, inspections, reports) sits at the top as the **operations and data** layer: missions, inspections, insights, reports. The system in this repo is the **engineering** layer under it, answering "why did that mission fail, and what's broken on the vehicle?"

---

## 2. Building it: the phases

### Phase 1 — Design for debuggability (before writing code)

1. **Run an FMEA.** List every failure mode (GPS loss, link loss, brownout, prop damage, lid jam, process crash, disk full, clock drift…), and for each one say **how it's detected, what the vehicle does on its own, and what a human needs to see**. This repo's `rules.py` and `rootcause.py` are that table turned into code.
2. **Choose hardware that recovers itself:**
   - A separate flight controller (MCU/RTOS) from the Linux companion, so a Linux crash ≠ a crash landing.
   - A hardware watchdog on the companion (`/dev/watchdog` driven by systemd `RuntimeWatchdogSec=`).
   - An independent safety system with its own power and arming logic.
   - Industrial storage (eMMC/NVMe with power-loss protection, *not* consumer SD cards).
   - A dual-SIM modem or two modems on **different carriers**; an external antenna.
   - Out-of-band power control at the base station (a cellular-controlled relay or a smart PDU), so you can power-cycle a hung computer remotely.
   - A GPS-disciplined clock (PPS → chrony). Without consistent time you can't correlate logs across systems.
3. **Define the lost-link behaviors** per mission phase and get them signed off (for drones, they also go in the regulatory beyond-visual-line-of-sight safety case).

### Phase 2 — The onboard software platform

| Concern | Ideal approach |
|---|---|
| OS | Immutable, read-only root filesystem with an **A/B partition** layout (RAUC, Mender, SWUpdate, or OSTree). A bad update boots back to the last good image automatically. |
| Processes | Each component is a systemd unit with `Restart=on-failure`, `WatchdogSec=` (the app calls `sd_notify("WATCHDOG=1")`), `MemoryMax=`, `CPUQuota=`. A leaking perception node gets killed and restarted, not the whole box. |
| Python | A pinned virtualenv baked into the image (no `pip install` in the field); `faulthandler` enabled; an `excepthook` that logs structured tracebacks; supervised threads (a dead thread must kill its process so systemd notices). |
| Middleware | ROS 2 / MAVLink router / ZeroMQ; topic rate monitoring (a silent topic is a fault). |
| Logging | Structured (JSON) logs to the journal with **persistent storage** and a size cap; flight logs (ULog/DataFlash) and rosbags in a rotating ring buffer. |
| Black box | A bounded, fsync'd local spool of health snapshots. It survives reboots and hard landings (`uplink.py` implements this). |
| Health agent | Read-only, resource-limited, runs on its own regardless of the network (`agent.py`). |
| Time | chrony with GPS/PPS and NTP; all logs in UTC. |
| Config | Versioned, delivered by the fleet config service, validated before it's applied, recorded in every health report. |
| Secrets | A per-device identity (X.509 cert in a TPM/secure element); no shared passwords. |

### Phase 3 — Connectivity design

**3.1 Assume the network is hostile and intermittent.**
- **Outbound-only.** Vehicles connect *out* to the cloud. Never require an inbound port: carrier CGNAT will block it anyway, and an open port is an attack surface.
- **Multi-link.** Bond or fail over between carriers, 5G, satellite (Starlink/Iridium for heartbeats), and local radio/mesh. Track which link is active in every report.
- **Encryption and identity everywhere.** mTLS or WireGuard, with device certificates you can revoke.

**3.2 Tier traffic by priority, not by type**

| Tier | Example | Size | When it's sent |
|---|---|---|---|
| P0 heartbeat | alive, status, GO/NO-GO, position | <200 B | Every 5–30 s, over any link including satellite/SMS |
| P1 events | new finding, failsafe, mission abort | ~1 KB | Immediately, retried, queued if offline |
| P2 summaries | compact diagnosis, metrics | 1–5 KB | Every cycle when the link is good |
| P3 full state | full snapshot, top-N logs | 10–100 KB | On status change, or every 10 min |
| P4 bulk | flight logs, rosbags, imagery, debug bundles | MB–GB | **Only at the base station / on Wi-Fi / unmetered**, resumable uploads |

This repo's `Uplink` implements P1–P3: compact vs. full, store-and-forward, at-least-once delivery.

**3.3 Protocols.** MQTT 5 (persistent sessions, QoS 1, small overhead) or HTTPS batches (simple, works through any proxy). Avoid chatty request/response protocols over cellular.

**3.4 Detect silence as a fault.** The cloud must tell "healthy and quiet" apart from "dead". Expected heartbeats that don't arrive → **SILENT** → automatic NO-GO, an alert, and the last known state shown (`console.Fleet.view()` does this).

### Phase 4 — Cloud / fleet platform

- **Ingest** → **time-series DB** (Timescale/Influx/Prometheus) for metrics, an **event store** for findings, and **object storage** for bundles and logs.
- **Rules run in two places.** On the vehicle (works offline, decides GO/NO-GO) and in the cloud (fleet-wide correlation: "every vehicle at site X lost GPS at 14:02" means a site-level cause such as jamming, a weather event, or a carrier outage, not a hardware fault).
- **Fleet registry**: hardware revision, firmware/software versions, config hash, and maintenance history per vehicle. Most fleet bugs turn out to be "only on hardware rev C with software ≥ 2.4".
- **OTA with staged rollouts**: canary 1 vehicle → 5% → 25% → 100%, with automatic halt if health metrics regress; never update a vehicle mid-mission.
- **Alerting**: alert on *changes in state* and on SLO burn, not on every poll (`integrations.Notifier`).
- **Trends**: recurring findings per vehicle/site are the maintenance backlog (`history.py`).

### Phase 5 — Testing before the field

| Level | What | Tools |
|---|---|---|
| Unit | rules, parsers, state machines | pytest |
| SIL | full autonomy stack against a simulator | PX4/ArduPilot SITL, Gazebo, AirSim |
| **Network chaos** | links that drop, add latency, lose packets, flap | `tc netem`, toxiproxy; e.g. `tc qdisc add dev wwan0 root netem loss 30% delay 800ms` |
| **Fault injection** | each FMEA fault | this repo's `--fault` flags; kill processes; fill the disk; unplug USB |
| HIL | real FC + companion on the bench, simulated physics | PX4 HIL, a power supply you can brown out |
| Soak | 72 h+ continuous mission cycling from the base station | leaks, log growth, thermal |
| Field pilot | a few sites, engineers on call | the full debugging ladder below |

Any field failure you can't reproduce in SIL/HIL is a gap in your simulation or your logging. Close it.

---

## 3. Debugging vehicles you can't reach: the escalation ladder

Use the lowest rung that answers the question. Each rung up costs more bandwidth, risk and human time.

```
 Rung 0  Passive telemetry      dashboards, heartbeats, findings, trends        (always on)
 Rung 1  Automatic diagnosis    rules + root-cause hypotheses + GO/NO-GO          (always on)
 Rung 2  On-demand pull         service logs, debug bundle, flight logs           (on request)
 Rung 3  Remote shell           just-in-time, audited reverse tunnel              (break-glass)
 Rung 4  Remote remediation     restart service, reboot, clear disk, re-calibrate (approved actions)
 Rung 5  Remote fix             config push, OTA patch, rollback to the A/B slot  (change control)
 Rung 6  Out-of-band recovery   power-cycle via relay, recovery partition, serial (box is unresponsive)
 Rung 7  Truck roll             on-site technician, with the bundle already in hand
```

### Rung 0–1: Know before you ask
Every report carries enough context that most incidents are diagnosed **without touching the vehicle**: findings with fix instructions, correlated root causes, software/config version, link quality, and the last N error lines. Run this repo's `demo` to see it.

### Rung 2: Pull, don't poke
- `GET /logs?unit=…`: allow-listed journal access, no shell needed.
- `GET /bundle`: one archive with the diagnosis, journal, dmesg, process list, USB tree, video devices, modem status, pip freeze and flight logs. Attach it to the ticket. **Collect once, analyze offline.**
- Flight-log analysis (`analyze-log`) gives a timeline of *what was already going wrong before the failsafe*.

### Rung 3: Remote shell, done safely
- **Reverse tunnels only**: the vehicle dials out (WireGuard/Tailscale/Teleport/AWS SSM/Cloudflare Tunnel). No inbound ports.
- **Just-in-time access**: a short-lived certificate issued per session, tied to a ticket, recorded (session recording), with two-person approval for armed or flying vehicles.
- **Never on a flying vehicle** unless the procedure requires it; prefer when it is at its base station.
- Use `tmux`/`mosh` so a link drop doesn't kill your session and leave a half-finished command.

### Rung 4: Pre-approved remediations
*Implemented in `actions.py`. See "How a remote action flows" below.*

A small, typed allow-list of actions (`restart_service(name)`, `reboot`, `clear_cache`, `trigger_ffc`, `recalibrate_compass_at_base`), each with a precondition (`vehicle disarmed and at its base station`), a timeout, and an automatic verify step (re-run diagnose). Many teams let the **vehicle run these itself** for known faults: self-healing that is logged and reported.

#### How a remote action flows

```
 operator (logged in) ──► console: POST /api/action {vehicle, action, params, ticket, reason}
                            │ builds envelope {action, params, operator, ts, expires, nonce}
                            │ signs it: HMAC-SHA256 with that vehicle's secret
             ┌──────────────┴───────────────┐
        pull vehicle                   push vehicle (CGNAT)
   POST /actions/run now           queued in the vehicle's mailbox; delivered in the
                                   response to its next uplink POST (no inbound port)
             └──────────────┬───────────────┘
                 vehicle verifies: signature · not expired · nonce unused
                 checks preconditions on LIVE state: disarmed · docked · …
                 runs the action → re-diagnoses → resolved / remaining / new
                 appends to the local audit log → result goes back to the console
```

Commands expire (5 minutes by default) because a "reboot" queued while a vehicle was offline must not fire hours later, when it may be mid-mission. Unknown state fails the precondition: with no telemetry, the vehicle can't prove it's disarmed, so it refuses.

### Rung 5: Fixes over the air
Config pushes and OTA updates follow the staged rollout. The A/B layout means **every remote update has a remote undo**. The device must confirm the update is healthy (agent says GO) within N minutes, or it rolls back on its own.

### Rung 6: When the computer itself is unresponsive
This is where the hardware choices from Phase 1 pay off:
- The hardware watchdog reboots a hung kernel automatically.
- The base station's out-of-band channel (separate modem + relay/BMC/serial console) lets you power-cycle or reach a console even when the main OS or main link is dead.
- A recovery partition boots a minimal image that phones home and accepts a re-flash.

### Rung 7: Truck roll, with everything prepared
The technician arrives with the bundle already analyzed, the likely part (prop, charging contacts, GPS cable) in hand, and a checklist generated from the findings. Success measure: **one visit, not two.**

### Debugging techniques that work at a distance

| Technique | Why it matters remotely |
|---|---|
| **Correlate across layers by timestamp** | FC log + journal + dmesg + base station log + modem log on one timeline. Most "mysteries" are a power or link event a few seconds earlier (`rootcause.py`, the `preceded_by` field in log analysis). |
| **Compare against the fleet** | "Only this vehicle" → hardware. "Every vehicle at this site" → environment/RF/carrier. "Every vehicle since v2.4" → software. |
| **Replay** | Pull the flight log/rosbag and replay it through the autonomy stack in SIL to reproduce the decision the vehicle made. |
| **Increase logging remotely, temporarily** | A config flag that raises verbosity for one subsystem for N hours, then reverts automatically. |
| **Keep snapshots before and after** | Capture state when a fault starts *and* when it clears; flapping faults hide in the gap. |
| **Health in the version string** | Every report includes the software version and config hash, so you can bisect across the fleet. |

---

## 4. Security (it's a remotely reachable robot)

- A per-device identity in hardware (TPM/secure element), mTLS, revocable certificates.
- Signed OTA images, verified boot where the SoC supports it.
- The health agent is **read-only** and resource-capped (see `deploy/fleetdebug-agent.service`); commands go through a separate, authenticated, audited path.
- Least privilege: the agent runs in the groups it needs (`systemd-journal`, `dialout`, `video`), not as root.
- Rate-limit and audit every remote action; alert on unusual access.
- Plan for GNSS spoofing/jamming detection (sudden position jumps, fleet-wide GPS loss at one site).

---

## 5. Metrics that tell you whether this works

| Metric | Target direction |
|---|---|
| Mission success rate (per site, per vehicle) | ↑ |
| Pre-flight availability (% of checks = GO) | ↑ (`history.availability`) |
| MTTD: mean time to detect a fault | ↓ (minutes, not "when the customer called") |
| MTTR: mean time to resolve | ↓ |
| % of incidents resolved without a site visit | ↑ (the most important one) |
| Silent-vehicle minutes | ↓ |
| Upload backlog age | ↓ |
| Recurring-fault count per vehicle | ↓ (`history.recurring`) |

---

## 6. What this repo implements vs. the full blueprint

| Blueprint item | Status here |
|---|---|
| Onboard health agent (Linux, Python, FC, base station, payloads, safety, uploads) | ✅ `collectors.py`, `telemetry.py`, `dock.py`, `payloads.py`, `agent.py` |
| Rules with fix instructions | ✅ `rules.py` |
| Root-cause correlation | ✅ `rootcause.py` |
| GO / HOLD / NO-GO gate | ✅ `preflight.py`, `GET /preflight`, `fleetdebug preflight` (exit codes for scripts) |
| Store-and-forward black box, push uplink, silent detection | ✅ `uplink.py`, `console.py` |
| Flight-log timeline with pre-failsafe context | ✅ `logs.py` (CSV; .ulg/.bin with pyulog/pymavlink) |
| Debug bundles, allow-listed remote logs | ✅ `bundle.py`, `/bundle`, `/logs` |
| Fleet dashboard, history/trends, alerts | ✅ `static/index.html`, `history.py`, `integrations.py` |
| Simulator + fault injection | ✅ `sim.py`, `--fault`, dashboard checkboxes |
| P0 heartbeat over satellite/SMS/LoRa | ✅ `heartbeat.py` (~70 bytes, checksummed), `uplink.fallback_cmd`, console `POST /api/heartbeat` |
| Pre-approved remote remediations (Rung 4) | ✅ `actions.py`: HMAC-signed, expiring, replay-proof commands; preconditions (disarmed/docked/FC link); before/after verification; audit log |
| Commands to vehicles behind CGNAT | ✅ mailbox: commands ride on the response to the vehicle's own uplink POST |
| Self-healing playbooks | ✅ `AutoHealer`: rate-limited, and escalates to a human when a fix doesn't stick |
| Console access control | ✅ HTTP Basic users (`fleetdebug hash-password`); the operator name goes into the audit log. Put an SSO proxy in front for production |
| Fleet-wide correlation | ✅ `fleetcorr.py`: site-level (environment/RF/carrier) vs. software-version (regression) patterns |
| Software/OTA visibility | ✅ version, A/B boot slot, RAUC/Mender detection, config hash in every report |
| Time-series metrics | ✅ Prometheus `/metrics` on the agent and console, so Grafana dashboards and SLO alerts plug straight in |
| MQTT transport | ⏳ next: an MQTT uplink beside HTTPS (same envelope, persistent sessions) |
| Remote shell broker (Rung 3) | 🔌 integrate WireGuard/Tailscale/Teleport; don't build your own |
| OTA / A/B updates (Rung 5) | 🔌 integrate RAUC/Mender/SWUpdate (the agent already reports slot + version) |
| Automatic rollout halt | ⏳ next: wire version-level incidents into the OTA server to pause a rollout |
| Analytics-platform integration | 🔌 `integrations.event_payload` is a versioned JSON event; point it at your platform's endpoint or middleware |
