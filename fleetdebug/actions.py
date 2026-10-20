"""Remote remediation: a small, typed allow-list of actions (rung 4 of the ladder).

Safety model:
  * Only actions defined here or in the config's `custom_actions` exist; there
    is no free-form shell.
  * Every command is an HMAC-signed envelope with an expiry and a nonce. A
    command queued for a vehicle that was offline must not run hours later, and
    a captured command must not be replayable.
  * Each action declares preconditions (disarmed, docked...). An unknown state
    counts as a failed precondition.
  * Each run is audited (who, ticket, why, before/after) and verified: the agent
    re-diagnoses and reports which findings cleared, stayed or appeared.

Commands reach the vehicle two ways, with the same envelope and checks:
  * pull mode: console -> POST /actions/run on the agent
  * push mode: piggy-backed on the response to the vehicle's own uplink POST,
    so it works behind CGNAT with no inbound port.
"""

import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import threading
import time

# ---------------------------------------------------------------- signing


def sign(envelope, secret):
    body = json.dumps({k: v for k, v in envelope.items() if k != "sig"}, sort_keys=True)
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def make_command(action, params, secret, operator, ticket="", reason="", ttl_s=300):
    now = time.time()
    env = {"action": action, "params": params or {}, "operator": operator,
           "ticket": ticket, "reason": reason, "ts": now, "expires": now + ttl_s,
           "nonce": secrets.token_hex(8)}
    env["sig"] = sign(env, secret)
    return env


class Verifier:
    def __init__(self, secret):
        self.secret = secret
        self.seen = {}  # nonce -> expires
        self.lock = threading.Lock()

    def check(self, env):
        if not self.secret:
            return "remote actions disabled: no action_secret configured on the vehicle"
        if not hmac.compare_digest(env.get("sig", ""), sign(env, self.secret)):
            return "bad signature"
        now = time.time()
        if env.get("expires", 0) < now:
            return f"command expired {int(now - env['expires'])}s ago"
        if env.get("ts", 0) > now + 120:
            return "command timestamp is in the future (clock skew?)"
        with self.lock:
            self.seen = {n: e for n, e in self.seen.items() if e > now}
            if env.get("nonce") in self.seen:
                return "replayed command"
            self.seen[env.get("nonce")] = env.get("expires", now)
        return None


# ---------------------------------------------------------------- preconditions


def _disarmed(snap):
    t = snap.get("telemetry") or {}
    if t.get("armed") is False:
        return True, "disarmed"
    if t.get("armed"):
        return False, "vehicle is ARMED"
    return None, "arming state unknown (no FC telemetry)"


def _docked(snap):
    d = snap.get("dock") or {}
    if d.get("available") and d.get("drone_present") is True:
        return True, "at base station"
    if d.get("available") and d.get("drone_present") is False:
        return False, "vehicle not at base station"
    return None, "base station state unknown"


def _link_ok(snap):
    t = snap.get("telemetry") or {}
    if t.get("heartbeat_age_s") is not None and t["heartbeat_age_s"] < 3:
        return True, "FC link ok"
    return False, "no FC heartbeat"


PRECONDITIONS = {"disarmed": _disarmed, "docked": _docked, "fc_link": _link_ok}


# ---------------------------------------------------------------- actions

def _run(argv, timeout=60):
    if not shutil.which(argv[0]):
        return {"ok": False, "output": f"{argv[0]} not found"}
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr)[-2000:]}


# What each action repairs in the simulator, so the demo behaves like the field:
# software and connectivity faults have remote fixes; hardware faults don't.
SIM_FIXES = {
    ("restart_service", "mission.service"): {"crashed_node", "service_disabled"},
    ("restart_service", "perception.service"): {"oom"},
    ("restart_service", "uploader.service"): {"upload_backlog"},
    ("reboot", None): {"crashed_node", "oom", "service_disabled", "dns_fail", "vpn_down"},
    ("vacuum_journal", None): {"disk_full"},
    ("restart_network", None): {"dns_fail", "vpn_down"},
    ("restart_vpn", None): {"vpn_down"},
    ("restart_modem", None): {"modem_hung"},
    ("switch_sim", None): {"sim_no_service"},
    ("resync_time", None): {"clock_skew"},
    ("restore_config", None): {"config_drift"},
    ("reupload_geofence", None): {"geofence_missing"},
}


def _sim(agent, action, key=None, output=None):
    with agent.lock:
        agent.faults -= SIM_FIXES.get((action, key), set())
    return {"ok": True, "output": output or f"(sim) {action} {key or ''}".strip()}


def a_restart_service(agent, params):
    unit = params.get("unit", "")
    if unit not in agent.config.get("watch_units", []):
        return {"ok": False, "output": f"unit not allow-listed: {unit}"}
    if agent.simulate:
        return _sim(agent, "restart_service", unit, f"(sim) restarted {unit}")
    return _run(["systemctl", "restart", unit])


def a_reboot(agent, params):
    if agent.simulate:
        return {**_sim(agent, "reboot", output="(sim) rebooted"), "no_verify": True}
    # Delay so the response/audit gets out before the network goes down.
    subprocess.Popen(["sh", "-c", "sleep 10 && systemctl reboot"])
    return {"ok": True, "output": "reboot scheduled in 10s", "no_verify": True}


def a_vacuum_journal(agent, params):
    size = str(params.get("max_size", "200M"))
    if not size[:-1].isdigit() or size[-1] not in "KMG":
        return {"ok": False, "output": "max_size must look like 200M"}
    if agent.simulate:
        return _sim(agent, "vacuum_journal", output=f"(sim) journal vacuumed to {size}")
    return _run(["journalctl", f"--vacuum-size={size}"])


def a_restart_modem(agent, params):
    if agent.simulate:
        return _sim(agent, "restart_modem", output="(sim) modem reset; link dropped ~30s")
    if shutil.which("mmcli"):
        return _run(["mmcli", "-m", "any", "--reset"])
    return {"ok": False, "output": "no ModemManager (mmcli) found"}


def a_restart_network(agent, params):
    if agent.simulate:
        return _sim(agent, "restart_network", output="(sim) network stack restarted")
    return _run(["systemctl", "restart", agent.config.get("network_unit", "NetworkManager.service")])


def a_restart_vpn(agent, params):
    if agent.simulate:
        return _sim(agent, "restart_vpn", output="(sim) VPN tunnel re-established")
    return _run(["systemctl", "restart", agent.config.get("vpn_unit", "wg-quick@wg0.service")])


def a_switch_sim(agent, params):
    """Fail over to the other SIM (second carrier)."""
    if agent.simulate:
        return _sim(agent, "switch_sim", output="(sim) switched to SIM 2")
    slots = agent.config.get("sim_slots", [1, 2])
    cur = int(params.get("current", slots[0]))
    nxt = slots[(slots.index(cur) + 1) % len(slots)] if cur in slots else slots[0]
    return _run(["mmcli", "-m", "any", f"--set-primary-sim-slot={nxt}"])


def a_resync_time(agent, params):
    """Step the clock now. A wrong clock breaks TLS, so uploads and the VPN fail."""
    if agent.simulate:
        return _sim(agent, "resync_time", output="(sim) clock stepped to GPS/NTP time")
    return _run(["chronyc", "makestep"])


def a_restore_config(agent, params):
    """Put back the approved copy of a config file someone edited by hand."""
    managed = {m["path"]: m for m in agent.config.get("managed_configs", [])}
    m = managed.get(params.get("path"))
    if not m and not agent.simulate:
        return {"ok": False, "output": f"not a managed config: {params.get('path')}"}
    if agent.simulate:
        return _sim(agent, "restore_config", output=f"(sim) restored {params.get('path')}")
    backup = m["path"] + ".rejected-" + time.strftime("%Y%m%d%H%M%S")
    shutil.copy2(m["path"], backup)  # keep the edited copy for the post-mortem
    tmp = m["path"] + ".tmp"
    shutil.copy2(m["baseline"], tmp)
    os.replace(tmp, m["path"])
    out = f"restored {m['path']} from baseline; edited copy kept at {backup}"
    if m.get("unit"):
        r = _run(["systemctl", "restart", m["unit"]])
        return {"ok": r["ok"], "output": out + "; " + r["output"]}
    return {"ok": True, "output": out}


def a_rollback_software(agent, params):
    """Boot the other A/B slot: the last software version that worked."""
    if agent.simulate:
        with agent.lock:
            if getattr(agent, "sim_version", "2.4.1") != "2.4.1":
                agent.sim_version = "2.4.1"
                agent.faults -= {"crashed_node", "oom"}
        return {"ok": True, "output": "(sim) rolled back to 2.4.1 (slot B) and rebooted",
                "no_verify": True}
    if shutil.which("rauc"):
        r = _run(["rauc", "status", "mark-active", "other"])
        if not r["ok"]:
            return r
        subprocess.Popen(["sh", "-c", "sleep 10 && systemctl reboot"])
        return {"ok": True, "output": "previous slot marked active; rebooting in 10s",
                "no_verify": True}
    return {"ok": False, "output": "no A/B update tool (rauc) found"}


def a_reupload_geofence(agent, params):
    if agent.simulate:
        return _sim(agent, "reupload_geofence", output="(sim) geofence re-uploaded to the FC")
    cmd = agent.config.get("geofence_upload_cmd")
    if not cmd:
        return {"ok": False, "output": "geofence_upload_cmd not configured"}
    return _run(cmd)


BUILTIN = {
    "restart_service": {"fn": a_restart_service, "preconditions": ["disarmed"],
                        "params": {"unit": "allow-listed systemd unit"},
                        "description": "Restart one allow-listed service"},
    "reboot": {"fn": a_reboot, "preconditions": ["disarmed", "docked"], "params": {},
               "description": "Reboot the companion computer (flight controller unaffected)"},
    "vacuum_journal": {"fn": a_vacuum_journal, "preconditions": [],
                       "params": {"max_size": "e.g. 200M"},
                       "description": "Shrink the systemd journal to free disk"},
    "restart_modem": {"fn": a_restart_modem, "preconditions": ["disarmed", "docked"],
                      "params": {}, "description": "Reset the cellular modem (link drops briefly)"},
    "restart_network": {"fn": a_restart_network, "preconditions": ["disarmed"], "params": {},
                        "description": "Restart the network stack (Wi-Fi/LTE/DNS)"},
    "restart_vpn": {"fn": a_restart_vpn, "preconditions": ["disarmed"], "params": {},
                    "description": "Re-establish the VPN tunnel to operations"},
    "switch_sim": {"fn": a_switch_sim, "preconditions": ["disarmed", "docked"], "params": {},
                   "description": "Fail over to the backup SIM / second carrier"},
    "resync_time": {"fn": a_resync_time, "preconditions": ["disarmed"], "params": {},
                    "description": "Correct the system clock (fixes TLS/upload failures)"},
    "restore_config": {"fn": a_restore_config, "preconditions": ["disarmed"],
                       "params": {"path": "managed config file"},
                       "description": "Restore an approved config that was edited by hand"},
    "rollback_software": {"fn": a_rollback_software, "preconditions": ["disarmed", "docked"],
                          "params": {}, "description": "Roll back to the previous software "
                                                       "version (A/B slot) and reboot"},
    "reupload_geofence": {"fn": a_reupload_geofence, "preconditions": ["disarmed", "docked"],
                          "params": {}, "description": "Re-upload the geofence to the flight controller"},
}


class ActionRunner:
    def __init__(self, agent):
        self.agent = agent
        cfg = agent.config
        self.verifier = Verifier(cfg.get("action_secret"))
        self.skip_pre = set(cfg.get("skip_preconditions", []))  # e.g. ["docked"] for rovers
        self.audit_path = cfg.get("audit_path") or (
            None if agent.simulate else "/var/lib/fleetdebug/audit.jsonl")
        self.audit_mem = []
        self.lock = threading.Lock()  # one action at a time
        self.actions = dict(BUILTIN)
        for name, spec in (cfg.get("custom_actions") or {}).items():
            argv, timeout = list(spec["argv"]), spec.get("timeout_s", 60)
            self.actions[name] = {
                "fn": (lambda a, p, argv=argv, name=name, timeout=timeout:
                       {"ok": True, "output": f"(sim) ran {name}"} if a.simulate
                       else _run(argv, timeout)),
                "preconditions": spec.get("preconditions", ["disarmed"]),
                "params": {}, "description": spec.get("description", " ".join(argv))}

    def check_preconditions(self, names, snap):
        out, ok = [], True
        for n in names:
            if n in self.skip_pre:
                out.append({"name": n, "ok": True, "detail": "skipped by config"})
                continue
            res, detail = PRECONDITIONS[n](snap)
            out.append({"name": n, "ok": res is True, "detail": detail})
            ok &= res is True
        return ok, out

    def catalog(self):
        snap = self.agent.snapshot()
        return {"enabled": bool(self.verifier.secret), "actions": [
            {"name": n, "description": a["description"], "params": a["params"],
             "preconditions": self.check_preconditions(a["preconditions"], snap)[1]}
            for n, a in self.actions.items()]}

    def run_signed(self, env):
        err = self.verifier.check(env)
        if err:
            return self._audit(env, {"ok": False, "status": "rejected", "error": err})
        return self.execute(env.get("action"), env.get("params") or {},
                            env.get("operator", "?"), env.get("ticket", ""),
                            env.get("reason", ""))

    def execute(self, name, params, operator, ticket="", reason=""):
        """Unsigned entry point: only for the local auto-healer, never exposed over HTTP."""
        env = {"action": name, "params": params, "operator": operator, "ticket": ticket,
               "reason": reason}
        spec = self.actions.get(name)
        if not spec:
            return self._audit(env, {"ok": False, "status": "rejected",
                                     "error": f"unknown action {name}"})
        if not self.lock.acquire(timeout=1):
            return self._audit(env, {"ok": False, "status": "rejected",
                                     "error": "another action is running"})
        try:
            before = self.agent.diagnose(heal=False)
            ok, pre = self.check_preconditions(spec["preconditions"], before["snapshot"])
            if not ok:
                return self._audit(env, {"ok": False, "status": "blocked",
                                         "preconditions": pre,
                                         "error": "precondition failed"})
            try:
                res = spec["fn"](self.agent, params)
            except Exception as exc:
                res = {"ok": False, "output": f"{type(exc).__name__}: {exc}"}
            result = {"ok": res["ok"], "status": "done" if res["ok"] else "failed",
                      "output": res.get("output", ""), "preconditions": pre}
            if res["ok"] and not res.get("no_verify"):
                time.sleep(self.agent.config.get("verify_after_s", 0 if self.agent.simulate
                                                  else 5))
                after = self.agent.diagnose(heal=False)
                b = {f["title"] for f in before["findings"]}
                a = {f["title"] for f in after["findings"]}
                result["verify"] = {"resolved": sorted(b - a), "remaining": sorted(b & a),
                                    "new": sorted(a - b), "status_before": before["status"],
                                    "status_after": after["status"]}
            return self._audit(env, result)
        finally:
            self.lock.release()

    def _audit(self, env, result):
        rec = {"ts": time.time(), "vehicle": self.agent.config.get("name"),
               **{k: env.get(k) for k in ("action", "params", "operator", "ticket", "reason")},
               **result}
        self.audit_mem = (self.audit_mem + [rec])[-200:]
        if self.audit_path:
            try:
                os.makedirs(os.path.dirname(self.audit_path), exist_ok=True)
                with open(self.audit_path, "a") as f:
                    f.write(json.dumps(rec, default=str) + "\n")
            except OSError as exc:
                rec["audit_error"] = str(exc)
        return rec


# Built-in self-healing ladders for the faults that cause most field incidents:
# connectivity and people errors. Each ladder is tried one step at a time, waiting
# `heal_step_wait_s` between steps to see if the last one worked; a step whose
# preconditions fail (vehicle flying, not docked) waits instead of being skipped.
# "{unit}" is filled in from the finding. Disable with "auto_remediate": [].
DEFAULT_PLAYBOOKS = [  # order matters: root causes first, generic symptoms last
    {"match": "Clock is off", "label": "clock keeps drifting", "component": "link", "ladder": [{"action": "resync_time"}]},
    {"match": "No cellular service", "label": "no cellular service on any SIM", "component": "link", "ladder": [
        {"action": "restart_modem"}, {"action": "switch_sim"}]},
    {"match": "Weak cellular link", "label": "weak cellular signal", "component": "link", "ladder": [
        {"action": "restart_modem"}, {"action": "switch_sim"}]},
    {"match": "edited outside the approved baseline", "label": "settings keep being changed", "ladder": [
        {"action": "restore_config", "params": {"path": "{path}"}}]},
    {"match": "is not running", "label": "software keeps crashing", "ladder": [
        {"action": "restart_service", "params": {"unit": "{unit}"}},
        {"action": "restart_service", "params": {"unit": "{unit}"}}, {"action": "reboot"}]},
    {"match": "systemd unit", "label": "a service keeps failing", "ladder": [
        {"action": "restart_service", "params": {"unit": "{unit}"}}, {"action": "reboot"}]},
    {"match": "Geofence not loaded", "label": "geofence won't load", "ladder": [{"action": "reupload_geofence"}]},
    {"match": "Disk /", "label": "disk keeps filling up", "ladder": [{"action": "vacuum_journal", "params": {"max_size": "200M"}}]},
    {"match": "Memory at", "label": "memory keeps running out", "ladder": [
        {"action": "restart_service", "params": {"unit": "perception.service"}}]},
    {"match": "not reaching the cloud", "label": "data still not uploading", "ladder": [
        {"action": "restart_service", "params": {"unit": "uploader.service"}},
        {"action": "restart_network"}]},
    {"match": "Cannot reach", "label": "can't reach operations", "component": "link", "ladder": [
        {"action": "restart_vpn"}, {"action": "restart_network"}, {"action": "restart_modem"},
        {"action": "switch_sim"}, {"action": "reboot"}]},
]


class AutoHealer:
    """Runs self-healing ladders on the vehicle, one step at a time, and escalates when spent.

    config "auto_remediate":
      omitted        -> DEFAULT_PLAYBOOKS
      []             -> self-healing off
      [playbooks]    -> your own; each {"match", "ladder": [{"action", "params"}...]}
                        (legacy {"match", "action", "params", "max_per_hour": N} = that
                        action retried N times)
    """

    def __init__(self, runner, playbooks, step_wait_s=60):
        if playbooks is None:
            playbooks = DEFAULT_PLAYBOOKS
        self.runner, self.step_wait_s = runner, step_wait_s
        self.playbooks = []
        for pb in playbooks:
            if "ladder" not in pb:
                pb = {"match": pb["match"], "max_per_hour": pb.get("max_per_hour", 3),
                      "ladder": [{"action": pb["action"], "params": pb.get("params", {})}] *
                      pb.get("max_per_hour", 3)}
            self.playbooks.append(pb)
        self.episodes = {}  # playbook index -> {"step", "last", "tried", ...}
        self.runs = {}  # playbook index -> [timestamps], across episodes

    def _params(self, step, finding):
        from .runbooks import _unit_for
        out = {}
        for k, v in (step.get("params") or {}).items():
            if v == "{unit}":
                v = _unit_for(finding, self.runner.agent.config)
            elif v == "{path}":
                v = finding.get("path") or finding.get("detail", "").split(" ")[0]
            out[k] = v
        return out

    def handle(self, result):
        """Runs at most one fix per call, then lets the next diagnosis show if it worked."""
        now = time.time()
        live = {}  # playbook index -> findings it owns
        for f in result.get("findings", []):
            if f["title"].startswith("Automatic fixes used up"):
                continue
            for i, pb in enumerate(self.playbooks):
                if pb["match"] in f["title"]:
                    live.setdefault(i, []).append(f)
                    break  # first matching playbook owns the finding
        self._forget(set(live), now)
        snap = result.get("snapshot") or {}
        # Steps already shown not to stick: no other ladder should repeat them.
        spent = {st for ep in self.episodes.values() if ep.get("flapping")
                 for st in ep.get("steps", [])}
        for i in sorted(live):
            pb, f = self.playbooks[i], live[i][0]
            ep = self.episodes.setdefault(i, {"step": 0, "last": 0, "tried": [],
                                              "match": pb.get("label", pb["match"]),
                                              "of": len(pb["ladder"]),
                                              "component": pb.get("component", "software")})
            ep["keys"] = [x.get("key") or x["title"] for x in live[i]]
            if ep["step"] >= len(pb["ladder"]):
                continue
            recent = [t for t in self.runs.get(i, []) if now - t < 3600]
            if len(recent) >= pb.get("max_per_hour", 6):
                # Each fix works but the problem keeps coming back: a deeper fault.
                ep["step"], ep["flapping"] = ep["of"], len(recent)
                continue
            if now - ep["last"] < self.step_wait_s:
                return []  # give the last fix time to take effect
            step = pb["ladder"][ep["step"]]
            spec = self.runner.actions.get(step["action"])
            params = self._params(step, f)
            sig = step["action"] + json.dumps(params, sort_keys=True)
            if not spec or None in params.values() or sig in spent:
                ep["step"] += 1
                continue
            ok, _ = self.runner.check_preconditions(spec["preconditions"], snap)
            if not ok:
                continue  # e.g. flying: try again once it is safe
            rec = self.runner.execute(step["action"], params, "auto-heal",
                                      reason=f"self-heal step {ep['step'] + 1}/{len(pb['ladder'])}"
                                             f": {f['title']}")
            ep["step"] += 1
            ep["last"] = now
            ep["tried"].append(step["action"])
            ep.setdefault("steps", []).append(sig)
            self.runs[i] = recent + [now]
            return [rec]
        return []

    def prune(self, findings):
        """Forget episodes whose problem is gone (fixed by an operator, or cleared)."""
        live = set()
        for f in findings:
            if f["title"].startswith("Automatic fixes used up"):
                continue
            for i, pb in enumerate(self.playbooks):
                if pb["match"] in f["title"]:
                    live.add(i)
                    break
        self._forget(live, time.time())

    def _forget(self, live, now):
        """Drop episodes whose problem is gone, except ones that keep coming back."""
        for i in set(self.episodes) - set(live):
            recent = [t for t in self.runs.get(i, []) if now - t < 3600]
            cap = self.playbooks[i].get("max_per_hour", 6)
            if self.episodes[i].get("flapping") and len(recent) >= cap:
                continue
            del self.episodes[i]

    def state(self):
        """Per finding key: how far along its ladder the vehicle is."""
        out = {}
        for ep in self.episodes.values():
            for key in ep.get("keys", []):
                out[key] = {"match": ep["match"], "step": ep["step"], "of": ep["of"],
                            "tried": list(ep["tried"]), "exhausted": ep["step"] >= ep["of"]}
        return out

    def escalations(self):
        out = []
        for ep in self.episodes.values():
            if ep["step"] >= ep["of"]:
                out.append({"severity": "critical", "component": ep["component"],
                            "title": f"Automatic fixes used up: {ep['match']}",
                            "detail": (f"The automatic fix worked {ep['flapping']} times in the "
                                       "last hour, but the problem keeps coming back."
                                       if ep.get("flapping") else
                                       "The vehicle tried " + ", then ".join(ep["tried"]) +
                                       "; the problem is still there."),
                            "fix": "Every automatic fix has been tried."})
        return out
