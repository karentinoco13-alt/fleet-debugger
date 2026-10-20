"""Prometheus text exposition for long-term graphs (Grafana) and SLO alerting."""

STATUS = {"ok": 0, "warning": 1, "critical": 2, "unreachable": 3}


def _esc(v):
    return str(v or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render(results):
    lines = []

    def metric(name, help_, typ="gauge"):
        lines.append(f"# HELP fleetdebug_{name} {help_}")
        lines.append(f"# TYPE fleetdebug_{name} {typ}")

    def sample(name, labels, value):
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, (int, float)):
            lab = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
            lines.append(f"fleetdebug_{name}{{{lab}}} {value}")

    series = [
        ("status", "0=ok 1=warning 2=critical 3=unreachable",
         lambda r, s: STATUS.get(r.get("status"), 3)),
        ("preflight_go", "1 if pre-flight decision is GO",
         lambda r, s: (r.get("preflight") or {}).get("decision") == "GO"),
        ("findings_critical", "critical findings",
         lambda r, s: sum(f["severity"] == "critical" for f in r.get("findings", []))),
        ("findings_warning", "warning findings",
         lambda r, s: sum(f["severity"] == "warning" for f in r.get("findings", []))),
        ("last_report_age_seconds", "seconds since the vehicle last reported",
         lambda r, s: r.get("age_s")),
        ("cpu_percent", "companion CPU", lambda r, s: (s.get("cpu") or {}).get("percent")),
        ("memory_percent", "companion memory", lambda r, s: (s.get("memory") or {}).get("percent")),
        ("soc_temp_celsius", "hottest thermal zone",
         lambda r, s: max([v for v in (s.get("temperatures") or {}).values()
                           if isinstance(v, (int, float))], default=None)),
        ("battery_volts", "battery voltage", lambda r, s: (s.get("telemetry") or {}).get("battery_voltage")),
        ("gps_satellites", "satellites", lambda r, s: (s.get("telemetry") or {}).get("gps_satellites")),
        ("vibration_max", "max IMU vibration m/s^2",
         lambda r, s: max((s.get("telemetry") or {}).get("vibration") or [None],
                          key=lambda v: v or 0)),
        ("fc_heartbeat_age_seconds", "flight-controller heartbeat age",
         lambda r, s: (s.get("telemetry") or {}).get("heartbeat_age_s")),
        ("cellular_rsrp_dbm", "dock cellular RSRP",
         lambda r, s: ((s.get("dock") or {}).get("cellular") or {}).get("rsrp_dbm")),
        ("upload_backlog_gb", "data waiting to upload", lambda r, s: (s.get("upload") or {}).get("size_gb")),
        ("enclosure_temp_celsius", "dock enclosure temperature",
         lambda r, s: (s.get("dock") or {}).get("enclosure_temp_c")),
    ]
    for name, help_, fn in series:
        metric(name, help_)
        for r in results:
            s = r.get("snapshot") or {}
            labels = {"vehicle": r.get("name"), "site": r.get("site"),
                      "version": (s.get("software") or {}).get("version")}
            try:
                sample(name, labels, fn(r, s))
            except Exception:
                pass
    return "\n".join(lines) + "\n"
