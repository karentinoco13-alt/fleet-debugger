"""Runbooks: turn each finding into "how do I actually fix this?".

Every finding gets:
  * route   - "remote" (fix from the console now), "wait" (it clears by itself;
              hold missions) or "site" (needs hands on the vehicle/base station)
  * steps   - ordered troubleshooting steps: confirm, fix, verify
  * action  - the remote action that fixes it, if one exists
  * verify  - what "fixed" looks like

Matching is by finding component + title keywords. The first match wins, so
specific entries go before general ones.
"""

import re

# Which systemd unit runs which watched process. Override with the
# `process_units` config key; these are the conventional defaults.
DEFAULT_PROCESS_UNITS = {"mission_node.py": "mission.service",
                         "perception_node.py": "perception.service",
                         "uploader": "uploader.service", "px4": "px4.service",
                         "mavlink-router": "mavlink-router.service"}

RUNBOOKS = [
    {"match": ("software", "automatic fixes used up"), "route": "remote",
     "action": "rollback_software",
     "steps": ["The vehicle restarted the software itself and it keeps failing: this is a "
               "software bug, not hardware. A technician can't fix it on site.",
               "If the fleet-pattern banner shows the same crash on one software version, "
               "roll this vehicle back to the previous version (button below).",
               "Pull the debug bundle for the developers and keep the faulty version paused.",
               "Only if the rollback doesn't help either: send someone to re-flash it."],
     "verify": "The vehicle runs the previous version and the crash is gone.",
     "bring": ["Laptop with a known-good software image on USB"]},
    {"match": ("link", "automatic fixes used up"), "route": "site",
     "steps": ["The vehicle already tried every connection fix: restarted the network and "
               "VPN, reset the modem, and switched to the backup SIM.",
               "Rule out a carrier outage first (carrier status page, other vehicles at the site).",
               "If it's only this vehicle: the antenna, cable or modem is faulty. Send someone."],
     "verify": "Signal better than -110 dBm and the vehicle reports normally.",
     "bring": ["Spare LTE antenna and cable", "Spare modem", "SIM from a second carrier"]},
    {"match": ("software", "is not running"), "route": "remote", "action": "restart_service",
     "steps": ["Open View service logs for the unit and find the last traceback: that is "
               "the bug to fix, the restart only buys time.",
               "Fix remotely: restart the service (needs the vehicle disarmed).",
               "If it crashes again within minutes, don't loop restarts: pull the debug "
               "bundle and compare the version against vehicles that are healthy.",
               "If only vehicles on one version crash (see the fleet-pattern banner), "
               "pause that rollout."],
     "verify": "The process is running and the systemd unit is active on the next check."},
    {"match": ("software", "edited outside the approved baseline"), "route": "remote",
     "action": "restore_config",
     "steps": ["Someone changed this file by hand on the vehicle. The vehicle restores the "
               "approved version itself and keeps the edited copy for review.",
               "Ask whoever made the change to submit it through the fleet config service, "
               "so it is reviewed and applied to every vehicle the same way."],
     "verify": "The file matches the approved baseline."},
    {"match": ("software", "systemd unit"), "route": "remote", "action": "restart_service",
     "steps": ["View service logs for the unit to see why it exited.",
               "Fix remotely: restart the unit.",
               "If it fails again immediately, the cause is config or a missing dependency: "
               "check the logs for 'No such file', 'ModuleNotFoundError' or permission errors."],
     "verify": "systemctl reports the unit active."},
    {"match": ("software", "python error"), "route": "remote", "action": "restart_service",
     "steps": ["View service logs and read the full traceback; note the file and line.",
               "If the process is still running, the error may be handled. Check whether "
               "missions complete before restarting anything.",
               "If the process died, restart its service; then fix the code path in the "
               "traceback and ship it through the staged rollout."],
     "verify": "No new Python errors in the journal over the next 15 minutes."},
    {"match": ("software", "required python modules"), "bring": ["Known-good software image on USB"], "route": "site",
     "steps": ["The service runs the wrong interpreter, or the virtualenv is broken.",
               "Check the interpreter path shown in the finding against the systemd unit's "
               "ExecStart.",
               "Re-flash or roll back the A/B image; don't pip install on a field vehicle."],
     "verify": "All required modules import."},
    {"match": ("compute", "oom kill"), "route": "remote", "action": "restart_service",
     "unit_hint": "perception.service",
     "steps": ["The kernel killed a process for lack of memory. The journal line names it.",
               "Restart the leaking service to recover now.",
               "Find the leak: memory that climbs between checks (see Trends) means a "
               "leak, usually an unbounded queue, cache or list in a ROS callback.",
               "Add MemoryMax= to that unit so a leak kills only it, not the flight stack."],
     "verify": "Memory stays flat across several checks after the restart."},
    {"match": ("compute", "memory at"), "route": "remote", "action": "restart_service",
     "unit_hint": "perception.service",
     "steps": ["Find the biggest process: it is usually the perception or video pipeline.",
               "Restart that service to reclaim memory.",
               "Watch the next few checks. If memory climbs again, it's a leak (see the "
               "OOM runbook), not a one-off spike."],
     "verify": "Memory below 90% and not rising."},
    {"match": ("compute", "cpu at"), "route": "remote", "action": "restart_service",
     "unit_hint": "perception.service",
     "steps": ["Check the SoC temperature first. Thermal throttling looks like high CPU.",
               "Find the hot process in the debug bundle (ps.txt is sorted by CPU).",
               "Restart a runaway node; cap camera/inference frame rates in its config."],
     "verify": "CPU below 90% on the next checks."},
    {"match": ("storage", "disk"), "route": "remote", "action": "vacuum_journal",
     "steps": ["Fix remotely: shrink the journal to free space.",
               "If still full, the culprit is flight logs or rosbags not being offloaded: "
               "check the upload queue.",
               "Set log rotation and a retention limit so it can't recur."],
     "verify": "Disk below 90%."},
    {"match": ("data-pipeline", ""), "route": "remote", "action": "restart_service",
     "unit_hint": "uploader.service",
     "steps": ["Check the base station's cellular signal first. With a weak link, data is queued, "
               "not lost.",
               "If the link is fine, restart the uploader service.",
               "Still stuck: check whether the cloud credentials or token expired (uploader "
               "logs show 401/403)."],
     "verify": "The upload queue shrinks on the next checks."},
    {"match": ("link", "clock is off"), "route": "remote", "action": "resync_time",
     "steps": ["The vehicle fixes this itself: it resyncs its clock.",
               "If it comes back, the time source is failing: check that the GPS has a fix "
               "and that NTP (UDP 123) isn't blocked by the carrier."],
     "verify": "Clock offset under 5 s, and uploads and the VPN reconnect."},
    {"match": ("link", "no cellular service"), "route": "remote", "action": "switch_sim",
     "steps": ["The vehicle fixes this itself: it resets the modem, then switches to the "
               "backup SIM.",
               "Check the carrier's status page for an outage at the site.",
               "If both SIMs have no service, it's the antenna or the modem: send someone."],
     "verify": "The modem is 'connected' and the vehicle reports normally."},
    {"match": ("link", "cannot reach"), "route": "remote", "action": "restart_network",
     "steps": ["The vehicle fixes this itself, one step at a time: restart the VPN, the "
               "network, then the modem, then switch SIM, then reboot.",
               "The error text says which layer failed: 'name resolution' means DNS, "
               "'timed out' means the VPN, 'Network is unreachable' means the modem or carrier.",
               "If every step has been tried and it's still down, send someone to check the "
               "modem, antenna and router."],
     "verify": "Every ops endpoint answers."},
    {"match": ("link", "weak cellular"), "route": "remote", "action": "restart_modem",
     "steps": ["If several vehicles at the site show it (fleet-pattern banner), it's the "
               "carrier: check the carrier status page and wait, or fail over to the second SIM.",
               "If only this base station: reset the modem remotely (the link drops ~30 s; the vehicle "
               "spools data meanwhile).",
               "If it persists, schedule a visit: check the antenna cable and mounting."],
     "verify": "RSRP better than -110 dBm and SINR above 0 dB."},
    {"match": ("link", "no heartbeat for"), "route": "wait",
     "steps": ["The vehicle stopped reporting. It keeps logging locally and backfills when "
               "it reconnects.",
               "Check the last report before it went quiet: weak signal or low power there "
               "points at the cause.",
               "Check the carrier status for the site and the base station's mains power.",
               "If still silent after an hour: power-cycle via the base station's out-of-band relay, "
               "then dispatch a technician."],
     "verify": "Reports resume, and the backlog is backfilled."},
    {"match": ("link", "agent unreachable"), "route": "wait",
     "steps": ["The console can't reach the agent. Check the VPN/tunnel to the vehicle first.",
               "If the vehicle also stopped pushing reports, treat it as silent (see above).",
               "If only the agent is down, its systemd unit will restart it automatically."],
     "verify": "The agent answers /health."},
    {"match": ("flight-controller", "heartbeat lost"), "bring": ["Spare flight-controller cable", "Multimeter"], "route": "remote", "action": "reboot",
     "steps": ["The companion computer lost contact with the flight controller.",
               "Check for a USB disconnect or under-voltage finding: they tell you whether "
               "it's the cable or power.",
               "Fix remotely: reboot the companion computer (needs disarmed + docked). This "
               "re-enumerates USB and restarts the MAVLink router.",
               "If it drops again, it's physical: schedule a visit to reseat or replace the "
               "FC cable and check the 5V supply under load."],
     "verify": "FC heartbeat under 3 s and no new USB disconnects."},
    {"match": ("link", "no serial device"), "bring": ["Spare flight-controller cable", "Multimeter"], "route": "remote", "action": "reboot",
     "steps": ["The flight controller's USB/serial device has disappeared from Linux.",
               "Try a remote reboot first: sometimes the USB hub just needs re-enumerating.",
               "If the device is still missing after the reboot: site visit to reseat the cable."],
     "verify": "/dev/ttyACM* or ttyTHS* is present and the FC heartbeat is back."},
    {"match": ("link", "usb disconnect"), "bring": ["Spare flight-controller USB cable", "Locking connectors or hot glue", "Powered USB hub"], "route": "site",
     "steps": ["Intermittent USB drops come from vibration on the connector or brownouts.",
               "Check whether they coincide with takeoff (high current) in the flight log.",
               "On the next visit: lock the connector, add strain relief, and power cameras "
               "and modems from a powered hub."],
     "verify": "No USB disconnects over several flights."},
    {"match": ("flight-controller", "unhealthy sensors"), "bring": ["Laptop with ground-control software for calibration"], "route": "site",
     "steps": ["Read which sensor is flagged in the finding detail.",
               "Compass: recalibrate away from the base station's steel. GPS: see the GPS runbook. "
               "Gyro/accel: recalibrate; if it persists, replace the FC."],
     "verify": "The FC sensor-health mask is clear."},
    {"match": ("flight-controller", "fc error message"), "bring": ["Laptop with ground-control software"], "route": "site",
     "steps": ["Look up the exact message in the PX4/ArduPilot docs; pre-arm messages name "
               "the failing check.",
               "Most pre-arm failures need calibration or a hardware check on site."],
     "verify": "Pre-arm checks pass."},
    {"match": ("gps", ""), "bring": ["Spare GPS antenna and cable"], "route": "wait",
     "steps": ["If several vehicles at one site lose GPS together (fleet-pattern banner), "
               "it's environmental (jamming, an obstruction, space weather). Hold missions "
               "and wait.",
               "If only this vehicle: check the flight log. Did it start when the LTE modem or "
               "camera started? That's RF interference from the vehicle itself.",
               "If it persists: site visit to check the antenna view and cable, and move the "
               "antenna away from USB3/LTE."],
     "verify": "3D fix, at least 8 satellites, HDOP under 2."},
    {"match": ("estimator", "compass"), "bring": ["Laptop with ground-control software", "External compass mast (if it recurs)"], "route": "site",
     "steps": ["Magnetic interference: new steel, cables or equipment near the base station?",
               "Recalibrate the compass away from the base station.",
               "If it returns right after calibration, mount an external compass on a mast."],
     "verify": "Compass variance under 0.8."},
    {"match": ("estimator", ""), "route": "wait",
     "steps": ["The EKF doesn't trust its position or velocity. It usually follows a GPS "
               "glitch or high vibration.",
               "Fix the underlying GPS or vibration finding; this clears by itself."],
     "verify": "EKF variances under 0.8."},
    {"match": ("airframe", "vibration"), "bring": ["Spare propeller set", "Spare motor", "Hex drivers", "Damping grommets"], "route": "site",
     "steps": ["No remote fix: this is mechanical.",
               "Keep the vehicle NO-GO. High vibration ruins the position estimate and "
               "can lead to a flyaway.",
               "On site: inspect and replace the props (chips, cracks), spin each motor by hand "
               "for rough bearings, and check the FC's damping mount."],
     "verify": "Vibration under 30 m/s² and no IMU clipping on a test hover."},
    {"match": ("power", "battery low"), "route": "wait",
     "steps": ["If the base station shows 'charging', wait. It clears when charged.",
               "If the base station is not charging, follow the charging-contacts runbook."],
     "verify": "Battery above the minimum voltage."},
    {"match": ("power", "under-voltage"), "bring": ["Multimeter", "Spare 5V regulator (BEC)"], "route": "site",
     "steps": ["The companion computer's 5V supply is sagging; this corrupts storage and "
               "causes random resets.",
               "On site: measure the rail under load and replace the BEC/regulator or cable."],
     "verify": "No under-voltage flags since boot."},
    {"match": ("power", "mains"), "bring": ["Site electrician contact"], "route": "site",
     "steps": ["The base station is running on its UPS. Check the site power feed.",
               "Hold missions if the UPS charge is low, so the drone can still land and charge."],
     "verify": "Mains power is restored."},
    {"match": ("power", "hot"), "route": "wait",
     "steps": ["Don't charge or fly hot packs. Wait for them to cool.",
               "If the base station HVAC also failed, follow that runbook."],
     "verify": "Pack temperature under 45 °C."},
    {"match": ("dock", "not charging"), "bring": ["Contact cleaner", "Lint-free cloths", "Multimeter"], "route": "site",
     "steps": ["Check where the drone landed: an off-center landing misses the contacts.",
               "High contact resistance means corrosion or dirt.",
               "On site: clean the contacts and pads, and check the charger output."],
     "verify": "The base station reports 'charging' and the battery rises."},
    {"match": ("dock", "lid"), "bring": ["Brush and de-icer", "Rail lubricant", "Spare limit switch"], "route": "site",
     "steps": ["Check the weather: ice and snow are the most common cause of a jammed lid.",
               "Don't keep retrying: the motor overheats.",
               "On site: clear the debris, check the limit switches, and lubricate the rails."],
     "verify": "The lid completes a cycle in under 40 s at normal current."},
    {"match": ("dock", "climate"), "bring": ["Replacement air filters", "Spare HVAC fan"], "route": "site",
     "steps": ["The base station's HVAC has failed; heat damages batteries and the computer.",
               "Hold missions in hot weather.",
               "On site: check the fans, filters and HVAC unit."],
     "verify": "Enclosure under 45 °C."},
    {"match": ("dock", ""), "bring": ["Basic toolkit", "Multimeter"], "route": "site",
     "steps": ["A base station fault needs a technician; the finding names the subsystem."],
     "verify": "The base station finding clears."},
    {"match": ("thermal", ""), "route": "wait",
     "steps": ["Usually the base station's climate control, or direct sun on the enclosure.",
               "Hold missions until it cools; fix the HVAC if that finding is also present."],
     "verify": "SoC temperature under 80 °C."},
    {"match": ("payload", "ffc"), "route": "remote", "action": "trigger_ffc",
     "steps": ["Fix remotely: trigger a flat-field correction.",
               "If it doesn't run, the camera's shutter may be stuck: site visit."],
     "verify": "Last FFC under 10 minutes ago."},
    {"match": ("payload", "not detected"), "route": "remote", "action": "reboot",
     "steps": ["The camera has disappeared from Linux.",
               "Try a remote reboot to re-enumerate USB/CSI.",
               "If it's still missing: site visit to reseat the payload connector."],
     "verify": "The camera device is present and streaming."},
    {"match": ("payload", "frozen"), "route": "remote", "action": "reboot",
     "steps": ["The camera is present but has stopped sending frames.",
               "Try a remote reboot; if a capture service is listed, restart that instead."],
     "verify": "A fresh frame within 5 s."},
    {"match": ("payload", "ogi"), "route": "wait",
     "steps": ["The gas camera's cooler needs a few minutes to reach temperature after power-on.",
               "If it never gets there, the cryocooler is failing: site visit."],
     "verify": "Cooler at about 77 K and cooldown complete."},
    {"match": ("payload", ""), "bring": ["Spare payload cable"], "route": "site",
     "steps": ["Check the payload connector and cable."], "verify": "The payload finding clears."},
    {"match": ("safety", "geofence"), "route": "remote", "action": "reupload_geofence",
     "steps": ["The mission reached the flight controller without its geofence. The vehicle "
               "re-uploads it itself once it is docked.",
               "If it keeps happening, check the mission-planning step that exports the fence."],
     "verify": "The flight controller reports the geofence loaded."},
    {"match": ("safety", ""), "bring": ["Parachute service kit", "Continuity tester"], "route": "site",
     "steps": ["No-fly until it's fixed. This is the last line of defense.",
               "On site: check pyro continuity, the safety system's battery and arming link, "
               "then rerun the self-test."],
     "verify": "Parachute armed and self-test passed."},
    {"match": ("weather", ""), "route": "wait",
     "steps": ["Expected: missions are on HOLD until the weather is inside limits.",
               "If it's calm on site but still reads high, the anemometer may be faulty."],
     "verify": "Wind and gusts inside the limits."},
]


def _unit_for(finding, cfg):
    units = list(cfg.get("watch_units", []))
    mapping = {**DEFAULT_PROCESS_UNITS, **(cfg.get("process_units") or {})}
    text = finding["title"] + " " + finding.get("detail", "")
    m = re.search(r"systemd unit (\S+)", text)
    if m:
        return m.group(1)
    for proc, unit in mapping.items():
        if proc in text and unit in units:
            return unit
    return None


def attach(findings, cfg, snapshot=None):
    """Adds a `runbook` to each finding (in place) and returns a per-vehicle plan."""
    units = cfg.get("watch_units", [])
    failed = [u for u, s in ((snapshot or {}).get("systemd") or {}).items()
              if s not in ("active", "unknown")]
    from .actions import BUILTIN
    actions = {*BUILTIN, *(cfg.get("custom_actions") or {})}
    for f in findings:
        # A key that survives changing numbers ("Memory at 96.3%" vs "97.1%").
        f["key"] = f["component"] + "|" + re.sub(r"\d+(\.\d+)?", "#", f["title"])
        title = f["title"].lower()
        component = f["component"]
        detail = f.get("detail", "").lower()
        # FC sensor alerts that name GPS or the compass follow those runbooks.
        if title.startswith("automatic fixes used up") and component not in ("software", "link"):
            component = "software"
        if component == "flight-controller" and "heartbeat" not in title:
            if "gps" in detail:
                component, title = "gps", "gps"
            elif "compass" in detail or "mag" in detail:
                component, title = "estimator", "compass"
        rb = next((r for r in RUNBOOKS if r["match"][0] == component
                   and r["match"][1] in title), None)
        if not rb:
            f["runbook"] = {"route": "site", "steps": [f.get("fix", "")], "verify": "",
                            "bring": []}
            continue
        out = {"route": rb["route"], "steps": rb["steps"], "verify": rb["verify"],
               "bring": rb.get("bring", [])}
        action = rb.get("action")
        if action == "restart_service":
            unit = _unit_for(f, cfg) or (failed[0] if failed else None) or rb.get("unit_hint")
            if unit in units:
                out["action"] = {"name": action, "params": {"unit": unit},
                                 "label": f"Restart {unit}"}
        elif action in actions:
            label = {"reboot": "Reboot companion computer", "vacuum_journal": "Free disk space",
                     "restart_modem": "Reset cellular modem", "trigger_ffc": "Trigger thermal FFC",
                     "restart_network": "Restart network", "restart_vpn": "Reconnect VPN",
                     "switch_sim": "Switch to backup SIM", "resync_time": "Fix the clock",
                     "restore_config": "Restore approved config",
                     "reupload_geofence": "Re-upload geofence",
                     "rollback_software": "Roll back to previous software"}.get(action, action)
            params = {}
            if action == "vacuum_journal":
                params = {"max_size": "200M"}
            elif action == "restore_config":
                params = {"path": f.get("detail", "").split(" ")[0]}
            out["action"] = {"name": action, "params": params, "label": label}
        if out["route"] == "remote" and "action" not in out:
            out["route"] = "site"  # the action isn't available on this vehicle
        f["runbook"] = out
    actionable = [f for f in findings if f["severity"] != "info"]
    plan = {r: sum(1 for f in actionable if f["runbook"]["route"] == r)
            for r in ("remote", "wait", "site")}
    if not actionable:
        plan["next"] = "Nothing to do."
    elif plan["remote"]:
        plan["next"] = "Start with the remote fixes, then re-check."
    elif plan["site"]:
        plan["next"] = "Needs a site visit. Take the debug bundle and the parts the runbooks list."
    else:
        plan["next"] = "Wait and hold missions; these clear by themselves."
    return plan
