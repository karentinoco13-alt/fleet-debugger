"""Payload, safety-system and data-pipeline collectors.

Covers what an inspection drone carries beyond the flight stack: RGB / radiometric
thermal / OGI (optical gas imaging) cameras, the parachute, and the on-drone
queue of captured data waiting to upload to the analytics platform.
"""

import glob
import json
import os
import time


def _safe(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
    wrapper.__name__ = fn.__name__
    return wrapper


@_safe
def cameras(payload_cfg):
    """payload_cfg: [{"name": "thermal", "kind": "thermal", "device": "/dev/video2",
                      "status_file": "/run/payload/thermal.json"}, ...]

    status_file is optional JSON written by the camera driver with any of:
    fps, frame_drops, sensor_temp_c, last_ffc_s (thermal), cooler_temp_k and
    cooldown_complete (cooled OGI cores), last_frame_s.
    """
    out = {}
    for p in payload_cfg:
        entry = {"kind": p.get("kind", "rgb"), "device": p.get("device")}
        dev = p.get("device")
        entry["present"] = bool(dev and (glob.glob(dev) if "*" in dev else os.path.exists(dev)))
        sf = p.get("status_file")
        if sf and os.path.exists(sf):
            with open(sf) as f:
                entry.update(json.load(f))
            entry["status_age_s"] = round(time.time() - os.path.getmtime(sf), 1)
        out[p["name"]] = entry
    return out


@_safe
def upload_queue(cfg):
    """Captured data still on the vehicle or base station that hasn't reached the cloud yet."""
    path = cfg.get("path")
    if not path or not os.path.isdir(path):
        return {"available": False}
    count, size, oldest = 0, 0, None
    for root, _, files in os.walk(path):
        for name in files:
            st = os.stat(os.path.join(root, name))
            count += 1
            size += st.st_size
            oldest = st.st_mtime if oldest is None else min(oldest, st.st_mtime)
    return {"available": True, "files": count, "size_gb": round(size / 1e9, 3),
            "oldest_age_h": round((time.time() - oldest) / 3600, 2) if oldest else 0}


@_safe
def safety(cfg):
    """Parachute / FTS status from a status file written by the safety controller."""
    sf = cfg.get("status_file")
    if not sf or not os.path.exists(sf):
        return {"available": False}
    with open(sf) as f:
        data = json.load(f)
    data["available"] = True
    data["status_age_s"] = round(time.time() - os.path.getmtime(sf), 1)
    return data
