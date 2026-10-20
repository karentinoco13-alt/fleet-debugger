"""Drone-in-a-box base station (dock) health.

Dock controllers are vendor-specific and their interfaces are not public, so
this module defines a small adapter interface. Ship-ready adapters:

  * HttpJsonDock - polls any HTTP endpoint that returns dock status JSON and
                   maps vendor field names onto ours via `field_map`.
  * FileDock     - reads a JSON status file that a vendor daemon writes.

Write your own adapter by subclassing DockAdapter and returning the
canonical fields listed in CANONICAL_FIELDS.
"""

import json
import time
import urllib.request

CANONICAL_FIELDS = {
    "lid_state": "open | closed | moving | fault",
    "lid_motor_current_a": "lid actuator current draw (jams show as spikes)",
    "lid_last_cycle_s": "seconds the last open/close took",
    "charging_state": "idle | charging | full | fault",
    "charge_contact_resistance_mohm": "contact resistance; rises with corrosion/dirt",
    "drone_present": "drone is seated on the pad",
    "drone_battery_temp_c": "pack temperature while docked",
    "enclosure_temp_c": "temperature inside the dock",
    "humidity_pct": "humidity inside the dock",
    "hvac_state": "ok | heating | cooling | fault",
    "mains_power": "mains power present",
    "ups_battery_pct": "UPS backup charge",
    "wind_mps": "weather station wind speed",
    "gust_mps": "weather station gust speed",
    "rain": "precipitation detected",
    "cellular": "{rsrp_dbm, sinr_db, rat: LTE/5G}",
    "landing_marker_ok": "precision-landing marker/beacon healthy",
}


class DockAdapter:
    def status(self):
        raise NotImplementedError


def _remap(raw, field_map):
    if not field_map:
        return raw
    out = {}
    for ours, theirs in field_map.items():
        cur = raw
        for part in theirs.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is not None:
            out[ours] = cur
    return out


class HttpJsonDock(DockAdapter):
    def __init__(self, url, field_map=None, token=None, timeout=3):
        self.url, self.field_map, self.token, self.timeout = url, field_map, token, timeout

    def status(self):
        req = urllib.request.Request(self.url)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return {"available": True, **_remap(json.load(r), self.field_map)}
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


class FileDock(DockAdapter):
    def __init__(self, path, field_map=None, max_age_s=30):
        self.path, self.field_map, self.max_age_s = path, field_map, max_age_s

    def status(self):
        import os
        try:
            age = time.time() - os.path.getmtime(self.path)
            with open(self.path) as f:
                data = _remap(json.load(f), self.field_map)
            return {"available": True, "stale": age > self.max_age_s,
                    "age_s": round(age, 1), **data}
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def from_config(cfg):
    if not cfg:
        return None
    kind = cfg.get("type")
    if kind == "http":
        return HttpJsonDock(cfg["url"], cfg.get("field_map"), cfg.get("token"))
    if kind == "file":
        return FileDock(cfg["path"], cfg.get("field_map"), cfg.get("max_age_s", 30))
    raise ValueError(f"unknown dock adapter type: {kind}")
