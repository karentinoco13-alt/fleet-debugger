"""Collect health data from a Linux-based onboard (companion) computer.

Everything here reads straight from /proc, /sys and standard CLI tools so the
agent runs on a stock Ubuntu/Debian/Yocto image with only the Python stdlib.
Each collector returns a plain dict and never raises: a failing collector
reports {"error": "..."} so one broken sensor can't take down the agent.
"""

import glob
import os
import platform
import shutil
import socket
import subprocess
import sys
import time


def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # collectors must never crash the agent
            return {"error": f"{type(exc).__name__}: {exc}"}
    wrapper.__name__ = fn.__name__
    return wrapper


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


@_safe
def cpu():
    def sample():
        with open("/proc/stat") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return idle, sum(parts)

    idle1, total1 = sample()
    time.sleep(0.2)
    idle2, total2 = sample()
    dt = total2 - total1
    usage = 100.0 * (1 - (idle2 - idle1) / dt) if dt else 0.0
    load1, load5, load15 = os.getloadavg()
    return {
        "percent": round(usage, 1),
        "cores": os.cpu_count(),
        "load": [load1, load5, load15],
    }


@_safe
def memory():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, val = line.split(":", 1)
            info[key] = int(val.split()[0])  # kB
    total = info["MemTotal"]
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    return {
        "total_mb": total // 1024,
        "available_mb": avail // 1024,
        "percent": round(100.0 * (total - avail) / total, 1),
        "swap_used_mb": (info.get("SwapTotal", 0) - info.get("SwapFree", 0)) // 1024,
    }


@_safe
def disks(paths=("/", "/var/log", "/data")):
    out = {}
    for p in paths:
        if os.path.exists(p):
            u = shutil.disk_usage(p)
            out[p] = {"free_gb": round(u.free / 1e9, 2),
                      "percent": round(100.0 * u.used / u.total, 1)}
    return out


@_safe
def temperatures():
    """Thermal zones (SoC on Jetson / Raspberry Pi / x86 NUCs)."""
    temps = {}
    for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
        raw = _read(os.path.join(zone, "temp"))
        if raw and raw.lstrip("-").isdigit():
            name = _read(os.path.join(zone, "type"), os.path.basename(zone))
            temps[name] = int(raw) / 1000.0
    return temps


@_safe
def throttling():
    """Raspberry Pi under-voltage / throttle flags, if vcgencmd exists."""
    if not shutil.which("vcgencmd"):
        return {"available": False}
    raw = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                         text=True, timeout=2).stdout.strip()
    value = int(raw.split("=")[1], 16)
    return {
        "available": True,
        "raw": hex(value),
        "under_voltage_now": bool(value & 0x1),
        "throttled_now": bool(value & 0x4),
        "under_voltage_since_boot": bool(value & 0x10000),
    }


@_safe
def processes(watch):
    """Check that each critical process (flight stack, ROS nodes, etc.) is alive."""
    found = {name: [] for name in watch}
    for pid_dir in glob.glob("/proc/[0-9]*"):
        cmdline = _read(os.path.join(pid_dir, "cmdline"), "")
        if not cmdline:
            continue
        cmdline = cmdline.replace("\x00", " ")
        for name in watch:
            if name in cmdline:
                pid = int(os.path.basename(pid_dir))
                stat = _read(os.path.join(pid_dir, "stat"), "").split()
                rss_pages = int(stat[23]) if len(stat) > 23 else 0
                found[name].append({
                    "pid": pid,
                    "state": stat[2] if len(stat) > 2 else "?",
                    "rss_mb": round(rss_pages * os.sysconf("SC_PAGE_SIZE") / 1e6, 1),
                })
    return {name: {"running": bool(p), "instances": p} for name, p in found.items()}


@_safe
def systemd_units(units):
    if not shutil.which("systemctl"):
        return {u: "unknown" for u in units}
    out = {}
    for u in units:
        r = subprocess.run(["systemctl", "is-active", u], capture_output=True,
                           text=True, timeout=3)
        out[u] = r.stdout.strip() or "unknown"
    return out


@_safe
def journal_errors(since="15 min ago", limit=50):
    if not shutil.which("journalctl"):
        return {"available": False, "entries": []}
    r = subprocess.run(
        ["journalctl", "-p", "err", "--since", since, "--no-pager", "-o", "short-iso",
         "-n", str(limit)],
        capture_output=True, text=True, timeout=5)
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith("--")]
    return {"available": True, "count": len(lines), "entries": lines[-limit:]}


@_safe
def kernel_events():
    """USB disconnects, serial errors, OOM kills — classic causes of lost FC links."""
    if not shutil.which("dmesg"):
        return {"available": False}
    r = subprocess.run(["dmesg", "--level=err,warn", "-T"], capture_output=True,
                       text=True, timeout=3)
    if r.returncode != 0:
        return {"available": False, "reason": r.stderr.strip()[:200]}
    keys = ("usb", "ttyACM", "ttyUSB", "ttyTHS", "oom", "Out of memory",
            "under-voltage", "I/O error", "segfault")
    hits = [l for l in r.stdout.splitlines() if any(k in l for k in keys)]
    return {"available": True, "count": len(hits), "entries": hits[-30:]}


@_safe
def serial_devices():
    patterns = ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/ttyTHS*", "/dev/serial/by-id/*")
    return sorted({p for pat in patterns for p in glob.glob(pat)})


@_safe
def network(hosts=()):
    ifaces = {}
    for iface in os.listdir("/sys/class/net"):
        if iface == "lo":
            continue
        ifaces[iface] = {
            "state": _read(f"/sys/class/net/{iface}/operstate", "unknown"),
            "rx_errors": int(_read(f"/sys/class/net/{iface}/statistics/rx_errors", "0")),
            "tx_errors": int(_read(f"/sys/class/net/{iface}/statistics/tx_errors", "0")),
        }
    reach = {}
    for host in hosts:
        h, _, port = host.partition(":")
        start = time.time()
        try:
            socket.create_connection((h, int(port or 80)), timeout=1).close()
            reach[host] = {"ok": True, "ms": round((time.time() - start) * 1000, 1)}
        except OSError as exc:
            reach[host] = {"ok": False, "error": str(exc)}
    return {"interfaces": ifaces, "reachability": reach}


@_safe
def python_env(required=()):
    import importlib.util
    mods = {m: importlib.util.find_spec(m) is not None for m in required}
    return {
        "version": sys.version.split()[0],
        "executable": sys.executable,
        "venv": sys.prefix != sys.base_prefix,
        "modules": mods,
    }


@_safe
def system_info():
    uptime = float(_read("/proc/uptime", "0 0").split()[0])
    return {
        "hostname": socket.gethostname(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "model": _read("/proc/device-tree/model", "").rstrip("\x00") or platform.node(),
        "uptime_s": int(uptime),
    }


@_safe
def software(config):
    """What is actually running: version, A/B slot, config hash.

    Every report carries these so a fault can be bisected across the fleet
    ("only on v2.4.1", "only on slot B after the update").
    """
    import hashlib
    import json as _json
    out = {"config_hash": hashlib.sha256(_json.dumps(config, sort_keys=True).encode())
           .hexdigest()[:12]}
    vf = config.get("version_file", "/etc/drone-release")
    out["version"] = config.get("software_version") or _read(vf, "unknown").splitlines()[0]
    cmdline = _read("/proc/cmdline", "")
    for tok in cmdline.split():  # RAUC / U-Boot / Mender set one of these
        if tok.startswith(("rauc.slot=", "slot_suffix=", "androidboot.slot_suffix=")):
            out["boot_slot"] = tok.split("=", 1)[1]
    if shutil.which("rauc"):
        r = subprocess.run(["rauc", "status", "--output-format=json"], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0:
            st = _json.loads(r.stdout)
            out["boot_slot"] = st.get("booted", out.get("boot_slot"))
            out["ota"] = {"tool": "rauc", "boot_primary": st.get("boot_primary")}
    elif os.path.exists("/data/mender/mender-store") or shutil.which("mender"):
        out["ota"] = {"tool": "mender",
                      "artifact": _read("/etc/mender/artifact_info", "").replace(
                          "artifact_name=", "")}
    return out


@_safe
def time_sync():
    """Clock offset. A clock that is minutes off breaks TLS (uploads, VPN) silently."""
    if shutil.which("chronyc"):
        r = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=3)
        info = dict(l.split(":", 1) for l in r.stdout.splitlines() if ":" in l)
        st = info.get("System time", "").split()
        offset = float(st[0]) * (-1 if "slow" in info.get("System time", "") else 1) if st else None
        return {"synced": "Normal" in info.get("Leap status", ""), "offset_s": offset,
                "source": info.get("Reference ID", "").strip()}
    if shutil.which("timedatectl"):
        r = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                           capture_output=True, text=True, timeout=3)
        return {"synced": r.stdout.strip() == "yes", "offset_s": None, "source": "timedatectl"}
    return {"available": False}


@_safe
def config_drift(managed):
    """Managed config files that no longer match their approved baseline."""
    import hashlib

    def digest(p):
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    drift = []
    for m in managed:
        if os.path.exists(m["path"]) and os.path.exists(m["baseline"]) and \
                digest(m["path"]) != digest(m["baseline"]):
            drift.append({"path": m["path"],
                          "changed_h": round((time.time() - os.path.getmtime(m["path"])) / 3600, 1),
                          "by": "unknown (not via the config service)"})
    return {"drift": drift}


def collect_all(config):
    return {
        "timestamp": time.time(),
        "system": system_info(),
        "cpu": cpu(),
        "memory": memory(),
        "disks": disks(config.get("disk_paths", ("/", "/var/log", "/data"))),
        "temperatures": temperatures(),
        "throttling": throttling(),
        "processes": processes(config.get("watch_processes", [])),
        "systemd": systemd_units(config.get("watch_units", [])),
        "journal": journal_errors(),
        "kernel": kernel_events(),
        "serial_devices": serial_devices(),
        "network": network(config.get("reachability_hosts", [])),
        "python": python_env(config.get("required_modules", [])),
        "software": software(config),
        "time": time_sync(),
        "config": config_drift(config.get("managed_configs", [])),
    }
