"""The demo fleet: simulated vehicles shared by `fleetdebug demo` and the static demo build."""

# Each demo vehicle: starting faults, plus how the demo plays them out.
#   preheal  - the vehicle already fixed these itself before the page opened
#   live     - the vehicle is mid-way through its self-healing ladder; the demo
#              plays the remaining steps live
#   flap     - the fault comes back after every restart (a software regression)
FLEET = [
    ("drone-01", "Refinery North", ["vpn_down", "clock_skew"], "2.4.1", "preheal"),
    ("drone-02", "Refinery North", ["vibration"], "2.4.1", None),
    ("drone-03", "Solar Farm A", ["gps_loss"], "2.4.1", None),
    ("drone-04", "Solar Farm A", ["crashed_node"], "2.5.0-rc1", "flap"),
    ("drone-05", "Mine Pit 3", ["modem_hung"], "2.4.1", "live"),
    ("drone-06", "Mine Pit 3", ["charge_contacts", "low_battery"], "2.4.1", None),
    ("drone-07", "Substation 12", ["config_drift", "geofence_missing"], "2.4.1", "preheal"),
    ("drone-08", "Substation 12", ["disk_full", "upload_backlog"], "2.4.1", "preheal"),
]
ROVERS = [
    ("rover-01", "Pipeline Corridor", ["service_disabled", "sim_no_service"], "2.4.1", "preheal"),
    ("rover-02", "Pipeline Corridor", ["cellular_weak"], "2.4.1", "live"),
]

# How long each problem has been going on when the demo opens (hours).
FAULT_AGE_H = {"vibration": 30, "gps_loss": 0.7, "crashed_node": 2.5, "modem_hung": 0.1,
               "charge_contacts": 9, "low_battery": 9, "cellular_weak": 0.3}


def vehicles(n_drones=8):
    """Yields {"cfg", "faults", "version", "push", "mode"} for each demo vehicle."""
    out = []
    for name, site, faults, version, mode in FLEET[:n_drones]:
        out.append({"cfg": {
            "name": name, "site": site, "action_secret": f"demo-secret-{name}",
            "watch_units": ["mission.service", "perception.service", "uploader.service",
                            "px4.service"],
            "custom_actions": {"trigger_ffc": {
                "argv": ["/opt/payload/bin/thermal-ffc"], "preconditions": [],
                "description": "Force a thermal-camera flat-field correction"}}},
            "faults": list(faults), "version": version, "push": False, "mode": mode})
    for name, site, faults, version, mode in ROVERS:
        out.append({"cfg": {
            "name": name, "site": site, "action_secret": f"demo-secret-{name}",
            "skip_preconditions": ["docked"],  # ground rovers have no dock
            "watch_units": ["mission.service"]},
            "faults": list(faults), "version": version, "push": True, "mode": mode})
    return out
