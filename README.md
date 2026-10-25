# Autonomous Fleet Debugger (fleetdebug)

**Live demo and case study: https://karentinoco13-alt.github.io/fleet-debugger/**

Remote debugging, self-healing and dispatch decisions for fleets of autonomous Linux/Python vehicles that depend on a network connection: drones that live in base stations, ground rovers, inspection robots and similar machines. It needs only the Python 3.8+ standard library (`pymavlink` and `pyulog` are optional).

It watches each vehicle's Linux and Python stack, its autopilot (MAVLink: PX4/ArduPilot), its base station, payloads (RGB / thermal / gas cameras), safety systems and data uploads. Vehicles fix common connectivity and settings problems themselves. For everything else, the console gives operators one plain-language decision per vehicle, from **No action needed** to **Send technician**, using explicit thresholds. It keeps working through connectivity loss.

**Read [BLUEPRINT.md](BLUEPRINT.md)** for the end-to-end architecture and the remote-debugging playbook.

## Try it (no hardware)

```bash
python3 -m fleetdebug demo            # 8 simulated drones + 2 push-mode rovers
# open http://127.0.0.1:8080
```

The demo runs 8 simulated drones and 2 ground rovers, each starting with different faults. Things to try:
- The header chips and each vehicle's decision: **OK**, **Fixing itself**, **Fix remotely**, **Wait**, **Schedule visit** or **Send technician**.
- drone-05 and rover-02 fix themselves live, one step at a time. drone-05 recovers when its modem is reset; rover-02 runs out of options (weak antenna) and switches to Send technician.
- drone-04 runs a software version that keeps crashing. After its own restarts fail, run **Roll back to previous software** (click it, then confirm).
- drone-06 needs a technician: open its work order and copy it.
- **Trends** shows how problems got resolved, and the dispatch rules in plain words.
- **Action log** shows every fix: who ran it (an operator or the vehicle itself) and what it resolved.

```bash
python3 -m fleetdebug diagnose --simulate --fault gps_loss --fault compass
python3 -m fleetdebug preflight --simulate --fault high_wind     # exit 0 GO / 1 HOLD / 2 NO-GO
python3 -m fleetdebug gen-log samples/flight.csv && python3 -m fleetdebug analyze-log samples/flight.csv
python3 -m fleetdebug diagnose        # real checks on this Linux machine
```

## Deploy

On each vehicle/dock computer:
```bash
deploy/install.sh                     # installs the systemd service
sudo nano /etc/fleetdebug/agent.json  # see deploy/agent.example.json
```
On the ops server:
```bash
python3 -m fleetdebug console -c deploy/console.example.json
```

There are two modes, and you can mix them in one fleet:
- **Pull**: the console polls `http://vehicle:8765/diagnose`. Use it on a LAN or VPN.
- **Push**: the vehicle sends diagnoses to the console's `/api/ingest` and spools to disk while offline (`"uplink"` in the agent config, or `agent --uplink URL --no-server`). Use this for cellular, CGNAT, or intermittent links.

## Agent API

| Endpoint | Purpose |
|---|---|
| `GET /diagnose` | findings, root causes, pre-flight decision, snapshot |
| `GET /preflight` | 200 = GO, 409 = HOLD/NO-GO (for mission-scheduler hooks) |
| `GET /logs?unit=X` | journal for an allow-listed unit |
| `GET /bundle` | debug bundle `.tar.gz` |
| `GET /actions` | remediation catalog with live precondition status |
| `POST /actions/run` | HMAC-signed command envelope (see `actions.py`) |
| `GET /audit`, `/metrics` | action audit trail, Prometheus metrics |
| `GET /snapshot`, `/health` | raw data, liveness |

Set `"token"` in the agent config to require `Authorization: Bearer <token>` on every endpoint.

## Remote actions and self-healing

Set `action_secret` on the vehicle and the same value on its console entry. Operators can then run allow-listed actions from the dashboard: restart a service, reboot, vacuum the journal, reset the modem, or anything in your `custom_actions`. Each action is signed, expires, is checked against live preconditions (disarmed, docked), is verified by re-diagnosing afterwards, and is audited. Push-mode vehicles receive actions in the response to their next uplink.

Use `auto_remediate` playbooks to let a vehicle fix known faults itself. They're rate-limited, and the vehicle escalates to a human if a fix doesn't stick.

## When to send a technician (dispatch policy)

Most incidents fix themselves. On the vehicle, without needing a connection, built-in
self-healing ladders handle:
- connectivity: VPN down, DNS broken, modem hung, SIM with no service, clock drift;
- people errors: a config edited by hand, a service someone stopped, a missing geofence, a full disk;
- crashed or leaking software.

Each ladder runs one step at a time: restart, reconnect, reset the modem, switch SIM, restore
the approved config, reboot. A crash that keeps coming back is offered a one-click software
rollback.

For every vehicle, the console turns what's left into one plain-language decision:
**No action needed**, **Fixing itself**, **Fix remotely**, **Wait**, **Schedule a visit** or
**Send a technician now**. When a technician is needed, it writes the work order for you:
what's broken, what was already tried, what to bring, and how to confirm the fix.

The thresholds live in the console config:

```json
"dispatch_policy": {
  "max_remote_attempts": 2,
  "wait_limit_h": {"gps": 2, "thermal": 2, "power": 4, "link": 1, "weather": null, "default": 4},
  "site_warning_within_h": 72
}
```

## Languages

The console, the demo, the case study and the blueprint are available in English and Spanish. Use the **EN | ES** switch in the header. The choice is remembered, and Spanish-language browsers start in Spanish. Translations live in `fleetdebug/static/i18n.js` and the blueprint in `BLUEPRINT.es.md`. `tests/test_i18n.py` fails if any engine message is missing a Spanish translation.

## Privacy and security

The **Privacy** button in the console header explains, in English and Spanish, where data goes. In the demo, everything runs in the browser with simulated vehicles, and only the language choice is saved. In a real deployment, data stays on the company's own console server. Remote actions are allow-listed, HMAC-signed, expiring and replay-protected, and every action is audited. Put the console behind a VPN or HTTPS and turn on operator sign-in.

## Console users
```bash
python3 -m fleetdebug hash-password      # paste the result into "users" in the console config
```

## Extend

- **A new check**: add a function decorated with `@rule` in `fleetdebug/rules.py`.
- **A new root-cause pattern**: add an entry to `HYPOTHESES` in `fleetdebug/rootcause.py`.
- **Your dock vendor**: use the `http` or `file` adapter with a `field_map`, or subclass `DockAdapter`.
- **A new simulated fault**: add it in `fleetdebug/sim.py`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Layout

```
fleetdebug/
  collectors.py   Linux: CPU, memory, disk, thermal, processes, systemd, journal, dmesg, serial, network, Python env
  telemetry.py    MAVLink reader (PX4/ArduPilot)
  dock.py         dock/base-station adapters
  payloads.py     cameras (RGB/thermal/OGI), parachute/safety, upload queue
  rules.py        diagnostic rules → findings with fixes
  rootcause.py    correlates findings into likely root causes
  preflight.py    GO / HOLD / NO-GO gate
  actions.py      signed remote actions, preconditions, verification, audit, self-healing
  fleetcorr.py    site-level vs. software-version incident correlation
  heartbeat.py    ~70-byte P0 heartbeat for SMS / satellite / LoRa
  metrics.py      Prometheus exposition
  uplink.py       store-and-forward push uplink (black-box spool)
  agent.py        on-vehicle HTTP API
  console.py      fleet console: polling, ingest, silent detection, dashboard API
  history.py      SQLite history: recurring faults, availability
  integrations.py Slack/webhook alerts, versioned event export
  bundle.py       debug bundles
  logs.py         flight-log analysis (CSV/.ulg/.bin) with failsafe context
  sim.py          simulator + fault injection
  static/         dashboard
deploy/           systemd unit, installer, example configs
tools/            static demo builder (tools/build_demo.py)
docs/             the published website (case study + demo), served by GitHub Pages
```

## License

Required Notice: Copyright (c) 2026 Karen Tinoco (https://www.thehumanelement.live)

Free to read, run and adapt for non-commercial purposes (personal projects, research, teaching, evaluation) under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). For commercial use, contact the author.
