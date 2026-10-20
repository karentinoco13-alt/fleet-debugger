"""Post-flight log analysis.

Supports:
  * CSV telemetry exports (columns: time_s plus any of the fields below)
  * PX4 .ulg logs when `pyulog` is installed
  * ArduPilot .bin dataflash logs when `pymavlink` is installed

Produces a timeline of events (when each problem started and how bad it got)
instead of just a pass/fail, which is what you actually need when debugging a
crash or an aborted mission.
"""

import csv
import os
import statistics

CHECKS = {
    # field: (direction, threshold, severity, message)
    "vibration_z": (">", 30, "warning", "High Z vibration"),
    "vibration_x": (">", 30, "warning", "High X vibration"),
    "vibration_y": (">", 30, "warning", "High Y vibration"),
    "gps_satellites": ("<", 6, "critical", "GPS satellite count dropped"),
    "gps_hdop": (">", 2.5, "warning", "GPS HDOP degraded"),
    "ekf_pos_variance": (">", 0.8, "critical", "EKF position variance high"),
    "ekf_compass_variance": (">", 0.8, "warning", "EKF compass variance high"),
    "cpu_percent": (">", 90, "warning", "Companion CPU saturated"),
    "soc_temp_c": (">", 80, "warning", "Companion SoC overheating"),
    "rssi": ("<", 30, "warning", "Weak radio link"),
}


def load_csv(path):
    with open(path, newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            row = {}
            for k, v in r.items():
                try:
                    row[k] = float(v)
                except (TypeError, ValueError):
                    row[k] = v
            rows.append(row)
    return rows


def load_ulog(path):
    from pyulog import ULog  # pip install pyulog
    ulog = ULog(path)
    data = {d.name: d.data for d in ulog.data_list}
    rows = {}

    def put(topic, field, out_name, scale=1.0):
        if topic in data and field in data[topic]:
            for ts, v in zip(data[topic]["timestamp"], data[topic][field]):
                t = round(ts / 1e6, 1)
                rows.setdefault(t, {"time_s": t})[out_name] = float(v) * scale

    put("vehicle_gps_position", "satellites_used", "gps_satellites")
    put("vehicle_gps_position", "hdop", "gps_hdop")
    put("battery_status", "voltage_v", "battery_voltage")
    put("battery_status", "current_a", "battery_current")
    put("vehicle_local_position", "z", "altitude_m", -1.0)
    put("vehicle_imu_status", "accel_vibration_metric", "vibration_z")
    return [rows[k] for k in sorted(rows)]


def load_dataflash(path):
    from pymavlink import mavutil
    mlog = mavutil.mavlink_connection(path)
    rows = {}
    fields = {"GPS": [("NSats", "gps_satellites"), ("HDop", "gps_hdop")],
              "BAT": [("Volt", "battery_voltage"), ("Curr", "battery_current")],
              "VIBE": [("VibeX", "vibration_x"), ("VibeY", "vibration_y"),
                       ("VibeZ", "vibration_z")],
              "XKF4": [("SP", "ekf_pos_variance"), ("SM", "ekf_compass_variance")]}
    while True:
        m = mlog.recv_match(type=list(fields))
        if m is None:
            break
        t = round(getattr(m, "TimeUS", 0) / 1e6, 1)
        for src, dst in fields[m.get_type()]:
            if hasattr(m, src):
                rows.setdefault(t, {"time_s": t})[dst] = float(getattr(m, src))
    return [rows[k] for k in sorted(rows)]


def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ulg":
        return load_ulog(path)
    if ext in (".bin", ".log"):
        return load_dataflash(path)
    return load_csv(path)


def _violates(v, op, thr):
    return isinstance(v, float) and (v > thr if op == ">" else v < thr)


def analyze(rows, checks=CHECKS):
    """Return {'summary':..., 'events':[...], 'stats':{...}}."""
    if not rows:
        return {"summary": "empty log", "events": [], "stats": {}}

    events = []
    for field, (op, thr, sev, msg) in checks.items():
        start = worst = None
        for r in rows:
            v = r.get(field)
            if _violates(v, op, thr):
                if start is None:
                    start, worst = r["time_s"], v
                worst = max(worst, v) if op == ">" else min(worst, v)
            elif start is not None:
                events.append(_event(sev, msg, field, start, r["time_s"], worst, thr))
                start = None
        if start is not None:
            events.append(_event(sev, msg, field, start, rows[-1]["time_s"], worst, thr))

    events.extend(_battery_sag(rows))
    events.extend(_telemetry_gaps(rows))
    events.sort(key=lambda e: e["start_s"])
    timeline = _mission_timeline(rows)
    for m in timeline:
        if m["critical"]:
            # What was already going wrong in the 30 s before a failsafe/abort?
            m["preceded_by"] = sorted({e["title"] for e in events
                                       if e["start_s"] <= m["time_s"]
                                       and e["end_s"] >= m["time_s"] - 30})

    stats = {}
    for field in sorted({k for r in rows for k in r if k != "time_s"}):
        vals = [r[field] for r in rows if isinstance(r.get(field), float)]
        if vals:
            stats[field] = {"min": round(min(vals), 2), "max": round(max(vals), 2),
                            "mean": round(statistics.fmean(vals), 2)}

    duration = rows[-1]["time_s"] - rows[0]["time_s"]
    crit = sum(e["severity"] == "critical" for e in events)
    return {
        "summary": f"{duration:.0f}s flight, {len(events)} event(s), {crit} critical",
        "duration_s": duration,
        "events": events,
        "timeline": timeline,
        "stats": stats,
    }


CRITICAL_EVENT_WORDS = ("failsafe", "abort", "rtl", "land", "parachute", "crash",
                        "emergency", "ekf", "lost")


def _mission_timeline(rows):
    """Mode changes and free-text events (CSV columns `mode` and `event`)."""
    out, prev_mode = [], None
    for r in rows:
        mode = r.get("mode")
        if isinstance(mode, str) and mode and mode != prev_mode:
            out.append({"time_s": r["time_s"], "type": "mode", "text": mode,
                        "critical": any(w in mode.lower() for w in CRITICAL_EVENT_WORDS[:3])})
            prev_mode = mode
        ev = r.get("event")
        if isinstance(ev, str) and ev:
            out.append({"time_s": r["time_s"], "type": "event", "text": ev,
                        "critical": any(w in ev.lower() for w in CRITICAL_EVENT_WORDS)})
    return out


def _event(sev, msg, field, start, end, worst, thr):
    return {"severity": sev, "title": msg, "field": field, "start_s": start,
            "end_s": end, "duration_s": round(end - start, 1),
            "worst": round(worst, 2), "threshold": thr}


def _battery_sag(rows, max_drop_v=1.0):
    """Sudden voltage drop under load = a weak cell or bad connector."""
    out = []
    prev = None
    for r in rows:
        v = r.get("battery_voltage")
        if isinstance(v, float):
            if prev and prev[1] - v > max_drop_v and r["time_s"] - prev[0] <= 2:
                out.append(_event("critical", "Battery voltage sag", "battery_voltage",
                                  prev[0], r["time_s"], v, prev[1] - max_drop_v))
            prev = (r["time_s"], v)
    return out


def _telemetry_gaps(rows, max_gap_s=2.0):
    out = []
    for a, b in zip(rows, rows[1:]):
        gap = b["time_s"] - a["time_s"]
        if gap > max_gap_s:
            out.append({"severity": "warning", "title": "Telemetry gap", "field": "time_s",
                        "start_s": a["time_s"], "end_s": b["time_s"],
                        "duration_s": round(gap, 1), "worst": round(gap, 1),
                        "threshold": max_gap_s})
    return out
