"""Diagnostic rules: turn a raw snapshot into prioritized findings.

Each rule is a function snapshot -> list[Finding]. Add your own by decorating
with @rule. Thresholds come from the config so they can be tuned per airframe.
"""

import os
from dataclasses import asdict, dataclass

from .telemetry import decode_sensor_mask

CRITICAL, WARNING, INFO = "critical", "warning", "info"
_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}

DEFAULT_THRESHOLDS = {
    "cpu_percent": 90, "mem_percent": 90, "disk_percent": 90, "temp_c": 80,
    "heartbeat_timeout_s": 3, "gps_min_sats": 8, "gps_max_hdop": 2.0,
    "vibration_warn": 30, "vibration_crit": 60, "ekf_variance": 0.8,
    "battery_min_v": 14.0, "comm_drop_percent": 5,
    "lid_current_a": 6.0, "lid_cycle_s": 40, "contact_mohm": 150,
    "enclosure_temp_c": 45, "dock_humidity_pct": 85, "battery_temp_c": 45,
    "wind_max_mps": 12, "gust_max_mps": 15, "rsrp_min_dbm": -110, "sinr_min_db": 0,
    "thermal_ffc_max_s": 600, "frame_stale_s": 5, "ogi_cooler_max_k": 85,
    "upload_backlog_h": 6, "upload_backlog_gb": 10,
}


@dataclass
class Finding:
    severity: str
    component: str
    title: str
    detail: str
    fix: str

    def to_dict(self):
        return asdict(self)


RULES = []


def rule(fn):
    RULES.append(fn)
    return fn


def _num(x):
    return isinstance(x, (int, float))


@rule
def check_cpu(s, t):
    pct = s.get("cpu", {}).get("percent")
    if _num(pct) and pct >= t["cpu_percent"]:
        yield Finding(WARNING, "compute", f"CPU at {pct}%",
                      "Sustained high CPU on the onboard computer delays perception "
                      "and control loops.",
                      "Run `top -H` to find the hot thread; check for runaway ROS "
                      "nodes or a vision pipeline without a frame-rate cap.")


@rule
def check_memory(s, t):
    m = s.get("memory", {})
    pct = m.get("percent")
    if _num(pct) and pct >= t["mem_percent"]:
        yield Finding(CRITICAL, "compute", f"Memory at {pct}%",
                      f"Only {m.get('available_mb')} MB available. The OOM killer may "
                      "terminate the flight software.",
                      "Look for leaks with `ps aux --sort=-rss | head`; add memory limits "
                      "(systemd MemoryMax=) to non-critical services.")
    for line in s.get("kernel", {}).get("entries", []) or []:
        if "Out of memory" in line or "oom" in line.lower():
            yield Finding(CRITICAL, "compute", "OOM kill detected in kernel log", line,
                          "Identify the killed process; reduce memory use or add swap/zram.")
            break


@rule
def check_disk(s, t):
    for path, d in (s.get("disks") or {}).items():
        if isinstance(d, dict) and _num(d.get("percent")) and d["percent"] >= t["disk_percent"]:
            yield Finding(WARNING, "storage", f"Disk {path} at {d['percent']}%",
                          f"{d['free_gb']} GB free. Flight logs and rosbags stop "
                          "recording when the disk fills.",
                          "Rotate logs (`journalctl --vacuum-size=200M`), offload rosbags, "
                          "set log retention.")


@rule
def check_thermal(s, t):
    for zone, c in (s.get("temperatures") or {}).items():
        if _num(c) and c >= t["temp_c"]:
            yield Finding(CRITICAL if c >= t["temp_c"] + 10 else WARNING, "thermal",
                          f"{zone} at {c:.1f}°C",
                          "SoC thermal throttling reduces compute and can cause missed "
                          "deadlines; common on vehicles parked in an enclosure in the sun.",
                          "Check fan/heatsink, enclosure ventilation, and ambient temperature.")
    th = s.get("throttling") or {}
    if th.get("under_voltage_now") or th.get("under_voltage_since_boot"):
        yield Finding(CRITICAL, "power", "Under-voltage on companion computer",
                      f"vcgencmd get_throttled = {th.get('raw')}",
                      "Check the BEC/5V regulator and wiring; under-voltage corrupts SD "
                      "cards and causes random resets.")


@rule
def check_processes(s, t):
    for name, p in (s.get("processes") or {}).items():
        if isinstance(p, dict) and not p.get("running"):
            yield Finding(CRITICAL, "software", f"Process '{name}' is not running",
                          "A watched critical process is missing.",
                          f"Check `journalctl -u <unit> -n 100` and restart. Search the "
                          f"logs for a Python traceback from {name}.")
        elif isinstance(p, dict) and any(i.get("state") == "Z" for i in p.get("instances", [])):
            yield Finding(WARNING, "software", f"Process '{name}' is a zombie",
                          "The process exited but its parent never reaped it.",
                          "Restart the parent service.")
    for unit, state in (s.get("systemd") or {}).items():
        if state not in ("active", "unknown"):
            yield Finding(CRITICAL if state == "failed" else WARNING, "software",
                          f"systemd unit {unit} is {state}", "",
                          f"`systemctl status {unit}` and `journalctl -u {unit} -b`")


@rule
def check_python_errors(s, t):
    entries = (s.get("journal") or {}).get("entries") or []
    tracebacks = [e for e in entries if "Traceback" in e or "Error:" in e or "Exception" in e]
    if tracebacks:
        yield Finding(WARNING, "software",
                      f"{len(tracebacks)} Python error line(s) in the journal (last 15 min)",
                      tracebacks[-1][:300],
                      "Run `journalctl -p err --since '15 min ago'` for the full stack trace.")
    py = s.get("python") or {}
    missing = [m for m, ok in (py.get("modules") or {}).items() if not ok]
    if missing:
        yield Finding(CRITICAL, "software", "Required Python modules missing",
                      ", ".join(missing),
                      f"Activate the right venv or `pip install {' '.join(missing)}`. "
                      f"Interpreter: {py.get('executable')}")


@rule
def check_links(s, t):
    if not s.get("serial_devices") and s.get("telemetry", {}).get("expects_serial"):
        yield Finding(CRITICAL, "link", "No serial device for the flight controller",
                      "No /dev/ttyACM*, ttyUSB* or ttyTHS* present.",
                      "Check the USB/UART cable; `dmesg -w` while replugging.")
    usb = [l for l in (s.get("kernel") or {}).get("entries", []) or []
           if "disconnect" in l.lower() and "usb" in l.lower()]
    if usb:
        yield Finding(WARNING, "link", f"{len(usb)} USB disconnect event(s)", usb[-1],
                      "Intermittent USB usually means vibration on a connector or power "
                      "brownouts. Secure the cable; use a powered hub for cameras/LTE.")
    for host, r in ((s.get("network") or {}).get("reachability") or {}).items():
        if not r.get("ok"):
            yield Finding(WARNING, "link", f"Cannot reach {host}", r.get("error", ""),
                          "Check the LTE/Wi-Fi link, VPN, and routing (`ip route`).")


@rule
def check_flight_controller(s, t):
    tel = s.get("telemetry") or {}
    if not tel.get("available"):
        if tel.get("error"):
            yield Finding(INFO, "flight-controller", "No MAVLink telemetry", tel["error"],
                          "Set `mavlink_url` in the config, e.g. serial:/dev/ttyACM0:921600 "
                          "or udpin:0.0.0.0:14550.")
        return

    hb = tel.get("heartbeat_age_s")
    if hb is None or hb > t["heartbeat_timeout_s"]:
        yield Finding(CRITICAL, "flight-controller", "Flight controller heartbeat lost",
                      f"Last heartbeat {hb}s ago.",
                      "Check the FC power and serial link, the baud rate, and whether "
                      "mavlink-router/MAVROS is holding the port.")

    mask = tel.get("unhealthy_sensor_mask") or 0
    if mask:
        yield Finding(CRITICAL, "flight-controller", "FC reports unhealthy sensors",
                      ", ".join(decode_sensor_mask(mask)) or hex(mask),
                      "Check the pre-arm messages in STATUSTEXT; recalibrate if it's the "
                      "compass/accel.")

    sats, hdop, fix = tel.get("gps_satellites"), tel.get("gps_hdop"), tel.get("gps_fix_type")
    if _num(fix) and fix < 3:
        yield Finding(CRITICAL, "gps", f"No 3D GPS fix (fix_type={fix})", "",
                      "Check the antenna's sky view and RF interference from the LTE "
                      "modem/camera; check the GPS cable.")
    elif _num(sats) and sats < t["gps_min_sats"]:
        yield Finding(WARNING, "gps", f"Low satellite count ({sats})", "",
                      "Check the antenna placement and nearby RF noise sources.")
    if _num(hdop) and hdop > t["gps_max_hdop"]:
        yield Finding(WARNING, "gps", f"High HDOP ({hdop})", "Poor position accuracy.",
                      "Wait for a better constellation, or check for multipath near the base station.")

    vib = [v for v in (tel.get("vibration") or []) if _num(v)]
    if vib and max(vib) >= t["vibration_warn"]:
        sev = CRITICAL if max(vib) >= t["vibration_crit"] else WARNING
        yield Finding(sev, "airframe", f"High vibration ({max(vib):.0f} m/s²)",
                      f"x/y/z = {vib}; clipping = {tel.get('clipping')}",
                      "Inspect props for chips/imbalance, motor bearings and FC mount "
                      "dampers. Clipping > 0 means the IMU is saturating.")

    for name, v in (tel.get("ekf_variances") or {}).items():
        if _num(v) and v >= t["ekf_variance"]:
            yield Finding(WARNING if v < 1.0 else CRITICAL, "estimator",
                          f"EKF {name} variance high ({v:.2f})", "",
                          "Compass: check for magnetic interference/recalibrate. Position: "
                          "GPS glitch. Velocity: vibration or optical-flow problem.")

    bv = tel.get("battery_voltage")
    if _num(bv) and 0 < bv < t["battery_min_v"]:
        yield Finding(CRITICAL, "power", f"Battery low ({bv:.2f} V)", "",
                      "Land/charge. If it's still low after a charge at the base station, check the "
                      "charging contacts and cell balance.")

    drop = tel.get("drop_rate_comm")
    if _num(drop) and drop >= t["comm_drop_percent"]:
        yield Finding(WARNING, "link", f"MAVLink packet drop {drop:.1f}%", "",
                      "Check the baud rate, cable shielding and CPU load on the companion.")

    for st in tel.get("statustext") or []:
        if _num(st.get("severity")) and st["severity"] <= 3:  # EMERGENCY..ERROR
            yield Finding(CRITICAL if st["severity"] <= 2 else WARNING,
                          "flight-controller", "FC error message", st.get("text", ""),
                          "Look up this message in the PX4/ArduPilot docs.")


@rule
def check_dock(s, t):
    d = s.get("dock") or {}
    if not d.get("available"):
        return
    if d.get("stale"):
        yield Finding(WARNING, "dock", "Base station status is stale", f"{d.get('age_s')}s old",
                      "The base station controller may have hung; restart it.")
    cur, cyc = d.get("lid_motor_current_a"), d.get("lid_last_cycle_s")
    if d.get("lid_state") == "fault" or (_num(cur) and cur > t["lid_current_a"]):
        yield Finding(CRITICAL, "dock", "Base station lid fault / actuator overcurrent",
                      f"state={d.get('lid_state')}, motor current={cur} A, last cycle={cyc}s",
                      "Inspect for ice, snow or debris on the rails; check the limit switches "
                      "and actuator. The vehicle can't leave or return until it's cleared.")
    elif _num(cyc) and cyc > t["lid_cycle_s"]:
        yield Finding(WARNING, "dock", f"Base station lid slow ({cyc}s cycle)", "",
                      "Lubricate the rails and check actuator wear before it fails.")
    res = d.get("charge_contact_resistance_mohm")
    if d.get("charging_state") == "fault" or (_num(res) and res > t["contact_mohm"]):
        yield Finding(CRITICAL, "dock", "Vehicle not charging at base station",
                      f"charging_state={d.get('charging_state')}, contact resistance={res} mΩ",
                      "Clean the charging contacts and pads (corrosion/dust); check the "
                      "vehicle stopped in position on its pads (landing or docking offset).")
    et, bt = d.get("enclosure_temp_c"), d.get("drone_battery_temp_c")
    if d.get("hvac_state") == "fault" or (_num(et) and et > t["enclosure_temp_c"]):
        yield Finding(CRITICAL, "dock", f"Base station climate control failure ({et}°C inside)",
                      f"hvac_state={d.get('hvac_state')}",
                      "Service the HVAC/fans and filters. High enclosure heat degrades "
                      "batteries and the companion computer.")
    if _num(bt) and bt > t["battery_temp_c"]:
        yield Finding(WARNING, "power", f"Battery pack hot at base station ({bt}°C)", "",
                      "Don't fast-charge hot packs; wait for them to cool or fix the HVAC.")
    if _num(d.get("humidity_pct")) and d["humidity_pct"] > t["dock_humidity_pct"]:
        yield Finding(WARNING, "dock", f"Base station humidity {d['humidity_pct']}%", "",
                      "Check the seals and desiccant; condensation risk for the electronics.")
    if d.get("mains_power") is False:
        yield Finding(CRITICAL, "power", "Base station on UPS: mains power lost",
                      f"UPS at {d.get('ups_battery_pct')}%", "Restore site power.")
    if d.get("landing_marker_ok") is False:
        yield Finding(CRITICAL, "dock", "Precision-landing marker unhealthy", "",
                      "Clean the marker/beacon; the vehicle may not be able to return to its base station.")
    cell = d.get("cellular") or {}
    rsrp, sinr = cell.get("rsrp_dbm"), cell.get("sinr_db")
    if cell.get("state") in ("searching", "denied", "no-service", "disabled"):
        yield Finding(CRITICAL, "link", f"No cellular service on SIM {cell.get('sim_slot', '?')}",
                      f"modem state: {cell.get('state')}",
                      "Usually a carrier outage or an expired SIM: fail over to the backup SIM.")
    if (_num(rsrp) and rsrp < t["rsrp_min_dbm"]) or (_num(sinr) and sinr < t["sinr_min_db"]):
        yield Finding(WARNING, "link", "Weak cellular link at the base station",
                      f"RSRP={rsrp} dBm, SINR={sinr} dB ({cell.get('rat')})",
                      "Expect video dropouts and upload delays. Check the antenna, "
                      "carrier outages, or add an external/MIMO antenna.")


@rule
def check_weather(s, t):
    d = s.get("dock") or {}
    w, g = d.get("wind_mps"), d.get("gust_mps")
    if (_num(w) and w > t["wind_max_mps"]) or (_num(g) and g > t["gust_max_mps"]):
        yield Finding(WARNING, "weather", f"Wind above limit ({w} m/s, gust {g})", "",
                      "Hold missions. If it's calm on site, check the weather-station anemometer.")
    if d.get("rain"):
        yield Finding(WARNING, "weather", "Precipitation detected", "",
                      "Hold missions unless the airframe is rated for rain.")


@rule
def check_payloads(s, t):
    for name, p in (s.get("payloads") or {}).items():
        if not isinstance(p, dict) or "error" in p:
            continue
        if not p.get("present"):
            yield Finding(CRITICAL, "payload", f"{name} camera not detected",
                          f"device {p.get('device')} missing",
                          "Check the payload connector and USB/CSI cable; `v4l2-ctl "
                          "--list-devices`; `dmesg | grep -i video`.")
            continue
        if _num(p.get("last_frame_s")) and p["last_frame_s"] > t["frame_stale_s"]:
            yield Finding(CRITICAL, "payload", f"{name} camera stream frozen",
                          f"last frame {p['last_frame_s']}s ago",
                          "Restart the capture service; check for a v4l2 `select timeout`.")
        if _num(p.get("frame_drops")) and p["frame_drops"] > 100:
            yield Finding(WARNING, "payload", f"{name} dropping frames ({p['frame_drops']})", "",
                          "Check USB bandwidth (move it to a separate controller) and CPU load.")
        if p.get("kind") == "thermal" and _num(p.get("last_ffc_s")) \
                and p["last_ffc_s"] > t["thermal_ffc_max_s"]:
            yield Finding(WARNING, "payload", "Thermal camera FFC overdue",
                          f"last flat-field correction {p['last_ffc_s']}s ago",
                          "Radiometric readings drift without FFC; trigger one, and check the "
                          "shutter mechanism.")
        if p.get("kind") == "ogi" and (p.get("cooldown_complete") is False or
                                       (_num(p.get("cooler_temp_k")) and
                                        p["cooler_temp_k"] > t["ogi_cooler_max_k"])):
            yield Finding(WARNING, "payload", "OGI camera cooler not at temperature",
                          f"cooler at {p.get('cooler_temp_k')} K",
                          "Gas detection is unreliable until cooldown completes; if it never "
                          "does, the cryocooler may be failing.")


@rule
def check_safety(s, t):
    sf = s.get("safety") or {}
    if not sf.get("available"):
        return
    bad = [k for k in ("parachute_armed", "self_test_passed", "pyro_continuity")
           if sf.get(k) is False]
    if bad:
        yield Finding(CRITICAL, "safety", "Parachute / flight-termination system not ready",
                      ", ".join(bad),
                      "No-fly until it's fixed. Check the pyro/ejection continuity, battery and "
                      "arming link; rerun the self-test.")
    m = s.get("mission") or {}
    if m.get("geofence_loaded") is False:
        yield Finding(CRITICAL, "safety", "Geofence not loaded on the FC", "",
                      "Re-upload the geofence before any flight.")


@rule
def check_time(s, t):
    tm = s.get("time") or {}
    off = tm.get("offset_s")
    if _num(off) and abs(off) > t.get("clock_max_offset_s", 5):
        yield Finding(CRITICAL, "link", f"Clock is off by {abs(off):.0f} s",
                      f"time source: {tm.get('source')}. A wrong clock makes TLS certificates "
                      "look invalid, so uploads and the VPN fail; logs also stop lining up.",
                      "Resync the clock (chronyc makestep); check the GPS time source and NTP.")


@rule
def check_config_drift(s, t):
    for d in (s.get("config") or {}).get("drift", []):
        yield Finding(WARNING, "software",
                      f"{os.path.basename(d['path'])} edited outside the approved baseline",
                      f"{d['path']} changed {d.get('changed_h', '?')} h ago by "
                      f"{d.get('by', 'unknown')}",
                      "Restore the approved version; make config changes through the "
                      "fleet config service, not by hand on the vehicle.")


@rule
def check_upload(s, t):
    u = s.get("upload") or {}
    if not u.get("available"):
        return
    if (_num(u.get("oldest_age_h")) and u["oldest_age_h"] > t["upload_backlog_h"]) or \
            (_num(u.get("size_gb")) and u["size_gb"] > t["upload_backlog_gb"]):
        yield Finding(WARNING, "data-pipeline", "Inspection data not reaching the cloud",
                      f"{u.get('files')} files / {u.get('size_gb')} GB queued, oldest "
                      f"{u.get('oldest_age_h')} h",
                      "Check the uploader service, cloud credentials/token expiry and "
                      "bandwidth. Reports and insights will be missing these flights.")


def diagnose(snapshot, thresholds=None):
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    findings = []
    for r in RULES:
        try:
            findings.extend(r(snapshot, t) or [])
        except Exception as exc:
            findings.append(Finding(INFO, "debugger", f"Rule {r.__name__} crashed",
                                    repr(exc), "Bug in the rule; report it."))
    findings.sort(key=lambda f: _ORDER[f.severity])
    return findings


def overall_status(findings):
    if any(f.severity == CRITICAL for f in findings):
        return "critical"
    if any(f.severity == WARNING for f in findings):
        return "warning"
    return "ok"


def overall_status_dicts(findings):
    sevs = {f["severity"] for f in findings}
    return "critical" if CRITICAL in sevs else "warning" if WARNING in sevs else "ok"
