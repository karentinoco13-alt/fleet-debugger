"""Flight-controller telemetry over MAVLink (PX4 / ArduPilot).

Uses pymavlink if installed. The agent works without it — telemetry just
reports as unavailable and the system-level checks still run.
"""

import threading
import time


class MavlinkMonitor:
    """Background reader that keeps the latest value of the messages we care about."""

    WANTED = ("HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT", "BATTERY_STATUS",
              "VIBRATION", "EKF_STATUS_REPORT", "ESTIMATOR_STATUS", "STATUSTEXT",
              "ATTITUDE", "GLOBAL_POSITION_INT", "RC_CHANNELS")

    def __init__(self, url):
        self.url = url
        self.latest = {}
        self.statustext = []
        self.last_heartbeat = None
        self.error = None
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        try:
            from pymavlink import mavutil
        except ImportError:
            self.error = "pymavlink not installed (pip install pymavlink)"
            return
        while True:
            try:
                conn = mavutil.mavlink_connection(self.url, autoreconnect=True)
                while True:
                    msg = conn.recv_match(type=list(self.WANTED), blocking=True, timeout=5)
                    if msg is None:
                        continue
                    self._ingest(msg.get_type(), msg.to_dict())
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                time.sleep(2)

    def _ingest(self, mtype, data):
        with self._lock:
            self.error = None
            if mtype == "HEARTBEAT":
                self.last_heartbeat = time.time()
            if mtype == "STATUSTEXT":
                self.statustext = (self.statustext + [
                    {"t": time.time(), "severity": data.get("severity"),
                     "text": data.get("text")}])[-50:]
            else:
                self.latest[mtype] = data

    def snapshot(self):
        with self._lock:
            hb_age = time.time() - self.last_heartbeat if self.last_heartbeat else None
            return normalize(self.latest, self.statustext, hb_age, self.error)


def normalize(latest, statustext, heartbeat_age, error=None):
    """Reduce raw MAVLink dicts to the fields the rules engine uses."""
    out = {"available": bool(latest) or heartbeat_age is not None,
           "error": error,
           "heartbeat_age_s": None if heartbeat_age is None else round(heartbeat_age, 2),
           "statustext": statustext[-20:]}

    hb = latest.get("HEARTBEAT")
    if hb:
        out["armed"] = bool(hb.get("base_mode", 0) & 128)
        out["system_status"] = hb.get("system_status")

    ss = latest.get("SYS_STATUS")
    if ss:
        out["battery_voltage"] = ss.get("voltage_battery", 0) / 1000.0
        out["battery_remaining"] = ss.get("battery_remaining")
        out["cpu_load_fc"] = ss.get("load", 0) / 10.0
        out["drop_rate_comm"] = ss.get("drop_rate_comm", 0) / 100.0
        present = ss.get("onboard_control_sensors_present", 0)
        enabled = ss.get("onboard_control_sensors_enabled", 0)
        health = ss.get("onboard_control_sensors_health", 0)
        out["unhealthy_sensor_mask"] = present & enabled & ~health

    gps = latest.get("GPS_RAW_INT")
    if gps:
        out["gps_fix_type"] = gps.get("fix_type")
        out["gps_satellites"] = gps.get("satellites_visible")
        out["gps_hdop"] = gps.get("eph", 9999) / 100.0

    vib = latest.get("VIBRATION")
    if vib:
        out["vibration"] = [vib.get("vibration_x"), vib.get("vibration_y"),
                            vib.get("vibration_z")]
        out["clipping"] = [vib.get("clipping_0"), vib.get("clipping_1"),
                           vib.get("clipping_2")]

    ekf = latest.get("EKF_STATUS_REPORT")
    if ekf:
        out["ekf_variances"] = {
            "velocity": ekf.get("velocity_variance"),
            "pos_horiz": ekf.get("pos_horiz_variance"),
            "pos_vert": ekf.get("pos_vert_variance"),
            "compass": ekf.get("compass_variance"),
        }
    est = latest.get("ESTIMATOR_STATUS")  # PX4 equivalent
    if est and "ekf_variances" not in out:
        out["ekf_variances"] = {
            "velocity": est.get("vel_ratio"),
            "pos_horiz": est.get("pos_horiz_ratio"),
            "pos_vert": est.get("pos_vert_ratio"),
            "compass": est.get("mag_ratio"),
        }
    return out


# Bit names for SYS_STATUS sensor masks (MAV_SYS_STATUS_SENSOR).
SENSOR_BITS = {
    0x1: "3D gyro", 0x2: "3D accel", 0x4: "3D mag", 0x8: "absolute pressure",
    0x20: "GPS", 0x40: "optical flow", 0x8000: "motor outputs",
    0x10000: "RC receiver", 0x200000: "AHRS", 0x2000000: "logging",
    0x4000000: "battery", 0x10000000: "prearm check",
}


def decode_sensor_mask(mask):
    return [name for bit, name in SENSOR_BITS.items() if mask & bit]
