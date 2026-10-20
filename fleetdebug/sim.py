"""Simulated vehicle with injectable faults, for developing and demoing without hardware."""

import math
import random
import time

FAULTS = {
    "gps_loss": "GPS antenna obstructed: fix lost, few satellites",
    "vibration": "Chipped propeller: high vibration and IMU clipping",
    "fc_link": "USB link to the flight controller dropped: no heartbeat",
    "overheat": "Onboard computer overheating in its enclosure",
    "oom": "Memory leak in the perception node",
    "crashed_node": "Python mission node crashed with a traceback",
    "compass": "Magnetic interference: compass variance high",
    "low_battery": "Battery depleted",
    "lid_jam": "Base station lid actuator jammed (ice/debris)",
    "charge_contacts": "Corroded charging contacts: vehicle not charging at base station",
    "hvac_fail": "Base station HVAC failed: enclosure overheating",
    "high_wind": "Wind above flight limit at the site",
    "cellular_weak": "Weak LTE signal at the base station",
    "thermal_cam": "Thermal camera missing / stale FFC",
    "ogi_cooldown": "OGI camera cooler not at temperature",
    "upload_backlog": "Captured data not uploading to the cloud",
    "parachute": "Parachute system not armed / self-test failed",
    # Connectivity and people errors: the bulk of real field incidents, all fixable remotely.
    "vpn_down": "VPN tunnel to operations dropped",
    "dns_fail": "DNS resolution broken after a network change",
    "modem_hung": "Modem attached but passing no data (needs a reset)",
    "sim_no_service": "Primary SIM has no service (carrier outage)",
    "clock_skew": "System clock drifted: TLS uploads and the VPN fail",
    "config_drift": "Someone edited mission.yaml by hand on the vehicle",
    "service_disabled": "Someone stopped the mission service and forgot to restart it",
    "geofence_missing": "Mission uploaded without its geofence",
    "disk_full": "Logs filled the disk",
}


def snapshot(name="sim-drone", faults=(), seed=None, version="2.4.1"):
    rnd = random.Random(seed)
    f = set(faults)
    now = time.time()
    wobble = math.sin(now / 5)

    procs = {
        "px4": {"running": True, "instances": [{"pid": 812, "state": "S", "rss_mb": 48.0}]},
        "mavlink-router": {"running": True,
                           "instances": [{"pid": 640, "state": "S", "rss_mb": 6.2}]},
        "mission_node.py": {"running": not f & {"crashed_node", "service_disabled"},
                            "instances": [] if f & {"crashed_node", "service_disabled"} else
                            [{"pid": 1204, "state": "S", "rss_mb": 120.0}]},
        "perception_node.py": {"running": True, "instances": [
            {"pid": 1301, "state": "R", "rss_mb": 3400.0 if "oom" in f else 850.0}]},
    }
    journal = []
    if "crashed_node" in f:
        journal = [
            "2026-10-20T10:01:12 drone mission_node.py[1204]: Traceback (most recent call last):",
            "2026-10-20T10:01:12 drone mission_node.py[1204]:   File \"mission_node.py\", line 88, in on_waypoint",
            "2026-10-20T10:01:12 drone mission_node.py[1204]: KeyError: 'next_wp' Exception in thread waypoint",
        ]
    kernel = []
    if "fc_link" in f:
        kernel.append("[Tue Oct 20 10:00:58 2026] usb 1-1.2: USB disconnect, device number 5")
    if "oom" in f:
        kernel.append("[Tue Oct 20 10:02:03 2026] Out of memory: Killed process 1290 (python3)")

    telemetry = {
        "available": True, "error": None,
        "heartbeat_age_s": 12.4 if "fc_link" in f else round(rnd.uniform(0.1, 0.9), 2),
        "armed": False, "system_status": 3,
        "battery_voltage": 13.1 if "low_battery" in f else round(16.4 + 0.1 * wobble, 2),
        "battery_remaining": 8 if "low_battery" in f else 86,
        "cpu_load_fc": 34.0, "drop_rate_comm": 0.2,
        "unhealthy_sensor_mask": 0x20 if "gps_loss" in f else (0x4 if "compass" in f else 0),
        "gps_fix_type": 1 if "gps_loss" in f else 3,
        "gps_satellites": 3 if "gps_loss" in f else rnd.randint(14, 19),
        "gps_hdop": 4.8 if "gps_loss" in f else round(rnd.uniform(0.6, 0.9), 2),
        "vibration": [72.0, 65.0, 81.0] if "vibration" in f else
                     [round(rnd.uniform(4, 9), 1) for _ in range(3)],
        "clipping": [12, 9, 40] if "vibration" in f else [0, 0, 0],
        "ekf_variances": {"velocity": 0.2, "pos_horiz": 0.9 if "gps_loss" in f else 0.1,
                          "pos_vert": 0.1, "compass": 1.2 if "compass" in f else 0.15},
        "statustext": ([{"t": now, "severity": 2, "text": "PreArm: Compass not healthy"}]
                       if "compass" in f else []),
    }

    return {
        "timestamp": now,
        "simulated": True,
        "active_faults": sorted(f),
        "system": {"hostname": name, "kernel": "5.15.0-tegra", "arch": "aarch64",
                   "model": "NVIDIA Jetson Orin NX (simulated)", "uptime_s": 86400},
        "cpu": {"percent": round(rnd.uniform(25, 45), 1), "cores": 8, "load": [1.2, 1.1, 1.0]},
        "memory": {"total_mb": 7600, "available_mb": 280 if "oom" in f else 4100,
                   "percent": 96.3 if "oom" in f else 46.0, "swap_used_mb": 0},
        "disks": {"/": {"free_gb": 1.1, "percent": 97.4} if "disk_full" in f else
                  {"free_gb": 41.2, "percent": 38.0}},
        "temperatures": {"CPU-therm": 91.5 if "overheat" in f else round(52 + 3 * wobble, 1),
                         "GPU-therm": 88.0 if "overheat" in f else 49.0},
        "throttling": {"available": False},
        "processes": procs,
        "systemd": {"px4.service": "active", "mavlink-router.service": "active",
                    "mission.service": "failed" if "crashed_node" in f else
                    ("inactive" if "service_disabled" in f else "active")},
        "journal": {"available": True, "count": len(journal), "entries": journal},
        "kernel": {"available": True, "count": len(kernel), "entries": kernel},
        "serial_devices": [] if "fc_link" in f else ["/dev/ttyACM0"],
        "network": {"interfaces": {"wwan0": {"state": "up", "rx_errors": 0, "tx_errors": 0}},
                    "reachability": _reach(f, rnd)},
        "time": {"synced": False, "offset_s": 412.0, "source": "none"} if "clock_skew" in f
                else {"synced": True, "offset_s": 0.003, "source": "GPS+NTP"},
        "config": {"drift": [{"path": "/etc/drone/mission.yaml", "changed_h": 3.2,
                              "by": "maintenance laptop (ssh)"}] if "config_drift" in f else []},
        "python": {"version": "3.10.12", "executable": "/opt/drone/venv/bin/python",
                   "venv": True, "modules": {"pymavlink": True, "numpy": True}},
        "software": {"version": version, "boot_slot": "A", "config_hash": "3f9a1c0b7d2e",
                     "ota": {"tool": "rauc", "boot_primary": "rootfs.0"}},
        "telemetry": {**telemetry, "expects_serial": True},
        "dock": {
            "available": True,
            "lid_state": "fault" if "lid_jam" in f else "closed",
            "lid_motor_current_a": 9.8 if "lid_jam" in f else 2.1,
            "lid_last_cycle_s": 61.0 if "lid_jam" in f else 18.0,
            "charging_state": "fault" if "charge_contacts" in f else
                              ("charging" if "low_battery" in f else "full"),
            "charge_contact_resistance_mohm": 420 if "charge_contacts" in f else 35,
            "drone_present": True,
            "drone_battery_temp_c": 47.0 if "hvac_fail" in f else 26.0,
            "enclosure_temp_c": 52.0 if "hvac_fail" in f else 24.0,
            "humidity_pct": 41,
            "hvac_state": "fault" if "hvac_fail" in f else "ok",
            "mains_power": True, "ups_battery_pct": 100,
            "wind_mps": 14.5 if "high_wind" in f else 4.2,
            "gust_mps": 19.0 if "high_wind" in f else 6.0,
            "rain": False,
            "cellular": {"rsrp_dbm": None if "sim_no_service" in f else
                         (-118 if "cellular_weak" in f else -86),
                         "sinr_db": None if "sim_no_service" in f else
                         (-3 if "cellular_weak" in f else 14), "rat": "LTE",
                         "state": "searching" if "sim_no_service" in f else "connected",
                         "sim_slot": 1},
            "landing_marker_ok": True,
        },
        "payloads": {
            "rgb": {"kind": "rgb", "device": "/dev/video0", "present": True, "fps": 30,
                    "frame_drops": 0, "last_frame_s": 0.1},
            "thermal": {"kind": "thermal", "device": "/dev/video2",
                        "present": "thermal_cam" not in f, "fps": 0 if "thermal_cam" in f else 9,
                        "sensor_temp_c": 38.0,
                        "last_ffc_s": 1900 if "thermal_cam" in f else 95,
                        "last_frame_s": 300 if "thermal_cam" in f else 0.2},
            "ogi": {"kind": "ogi", "device": "/dev/video4", "present": True, "fps": 15,
                    "cooler_temp_k": 118 if "ogi_cooldown" in f else 77,
                    "cooldown_complete": "ogi_cooldown" not in f, "last_frame_s": 0.1},
        },
        "upload": {"available": True,
                   "files": 2140 if "upload_backlog" in f else 3,
                   "size_gb": 38.5 if "upload_backlog" in f else 0.2,
                   "oldest_age_h": 31.0 if "upload_backlog" in f else 0.1},
        "safety": {"available": True,
                   "parachute_armed": "parachute" not in f,
                   "self_test_passed": "parachute" not in f,
                   "pyro_continuity": "parachute" not in f,
                   "status_age_s": 1.0},
        "mission": {"geofence_loaded": "geofence_missing" not in f, "home_set": True, "last_mission_result":
                    "aborted" if f & {"gps_loss", "fc_link", "low_battery"} else "completed"},
    }


def _reach(f, rnd):
    """Reachability of the ops endpoints, as the agent's network collector reports it."""
    def ok():
        return {"ok": True, "ms": round(rnd.uniform(40, 90), 1)}
    if f & {"modem_hung", "sim_no_service"}:
        down = {"ok": False, "error": "[Errno 101] Network is unreachable"}
        return {"ops.example.com:443": down, "10.8.0.1:51820": down}
    if "clock_skew" in f:
        return {"ops.example.com:443": {"ok": False, "error": "TLS: certificate is not yet valid"},
                "10.8.0.1:51820": ok()}
    return {
        "ops.example.com:443": {"ok": False, "error": "[Errno -3] Temporary failure in name "
                                "resolution"} if "dns_fail" in f else ok(),
        "10.8.0.1:51820": {"ok": False, "error": "timed out"} if "vpn_down" in f else ok(),
    }


def flight_log_rows(duration_s=300, hz=2, faults=("vibration", "gps_loss"), seed=1):
    """Generate a CSV-style flight log with faults injected mid-flight."""
    rnd = random.Random(seed)
    rows = []
    for i in range(int(duration_s * hz)):
        t = i / hz
        phase = t / duration_s
        row = {
            "time_s": t,
            "altitude_m": round(min(40.0, t * 2) if phase < 0.9 else max(0, 40 - (t - 0.9 * duration_s) * 2), 2),
            "battery_voltage": round(16.8 - 2.4 * phase + rnd.uniform(-0.05, 0.05), 2),
            "gps_satellites": float(rnd.randint(14, 18)),
            "gps_hdop": round(rnd.uniform(0.6, 0.9), 2),
            "vibration_x": round(rnd.uniform(5, 10), 1),
            "vibration_y": round(rnd.uniform(5, 10), 1),
            "vibration_z": round(rnd.uniform(8, 14), 1),
            "ekf_pos_variance": round(rnd.uniform(0.05, 0.2), 2),
            "cpu_percent": round(rnd.uniform(30, 55), 1),
            "soc_temp_c": round(50 + 15 * phase, 1),
        }
        if "vibration" in faults and 0.4 < phase < 0.6:
            row["vibration_z"] = round(rnd.uniform(35, 60), 1)
        if "gps_loss" in faults and 0.7 < phase < 0.75:
            row["gps_satellites"] = 4.0
            row["gps_hdop"] = 3.8
            row["ekf_pos_variance"] = 1.1
        if "battery_sag" in faults and abs(phase - 0.5) < 0.004:
            row["battery_voltage"] -= 1.6
        row["mode"] = ("TAKEOFF" if phase < 0.05 else "MISSION" if phase < 0.9 else "LAND")
        row["event"] = ""
        if i == 0:
            row["event"] = "Lid open, launch"
        if "gps_loss" in faults and 0.75 <= phase:
            row["mode"] = "RTL" if phase < 0.9 else "LAND"
            if abs(phase - 0.75) < 1 / (duration_s * hz):
                row["event"] = "Failsafe: GPS lost, mission aborted, RTL"
        rows.append(row)
    return rows
