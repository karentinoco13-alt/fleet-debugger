"""On-vehicle (or base-station) agent: an HTTP JSON API for health, diagnosis and debugging.

Endpoints (all GET unless noted; Bearer token auth if `token` is configured):
  /health                   liveness
  /snapshot                 raw collected data
  /diagnose                 findings + root causes + preflight decision
  /preflight                go/no-go only (for mission-scheduler hooks)
  /logs?unit=X&lines=N      journal for an allow-listed systemd unit
  /bundle                   download a debug bundle (.tar.gz)
  /actions                  remediation catalog with live precondition status
  /audit                    recent remediation audit records
  /metrics                  Prometheus metrics for this vehicle
  POST /actions/run         HMAC-signed command envelope (see actions.py)
  POST /faults              (simulator only) {"faults": [...]}

Diagnosis is read-only. The only way to change the vehicle is a signed,
allow-listed, precondition-checked action; the vehicle is never flown from here.
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import (actions, bundle, collectors, dock, metrics, payloads, preflight, rootcause,
               rules, runbooks, sim)
from .telemetry import MavlinkMonitor


class Agent:
    def __init__(self, config, simulate=False, faults=()):
        self.config = config
        self.simulate = simulate
        self.faults = set(faults)
        self.lock = threading.Lock()
        self.mav = None
        self.dock = None
        if not simulate:
            if config.get("mavlink_url"):
                self.mav = MavlinkMonitor(config["mavlink_url"]).start()
            self.dock = dock.from_config(config.get("dock"))
        self.runner = actions.ActionRunner(self)
        self.healer = actions.AutoHealer(self.runner, config.get("auto_remediate"),
                                         config.get("heal_step_wait_s", 60))
        self.last_auto_actions = []

    @property
    def name(self):
        return self.config.get("name") or collectors.system_info().get("hostname")

    def snapshot(self):
        if self.simulate:
            with self.lock:
                # A software regression: the crash comes back until the version is rolled back.
                if getattr(self, "sim_flap", None) and getattr(self, "sim_version",
                                                                "2.4.1") != "2.4.1":
                    self.faults |= self.sim_flap
                snap = sim.snapshot(self.config.get("name", "sim-drone"), self.faults,
                                    version=getattr(self, "sim_version", "2.4.1"))
            snap["name"] = self.config.get("name", "sim-drone")
            return snap
        cfg = self.config
        snap = collectors.collect_all(cfg)
        if self.mav:
            snap["telemetry"] = self.mav.snapshot()
        else:
            snap["telemetry"] = {"available": False, "error": "mavlink_url not configured"}
        snap["telemetry"]["expects_serial"] = str(cfg.get("mavlink_url", "")).startswith(
            ("serial:", "/dev/"))
        snap["dock"] = self.dock.status() if self.dock else {"available": False}
        snap["payloads"] = payloads.cameras(cfg.get("payloads", []))
        snap["upload"] = payloads.upload_queue(cfg.get("upload", {}))
        snap["safety"] = payloads.safety(cfg.get("safety", {}))
        snap["name"] = self.name
        return snap

    def diagnose(self, heal=False):
        result = self._diagnose()
        if heal and self.healer.playbooks:
            ran = self.healer.handle(result)
            if ran:
                self.last_auto_actions = (self.last_auto_actions + ran)[-20:]
                result = self._diagnose()
        result["auto_actions"] = self.last_auto_actions[-5:]
        result["healing"] = self.healer.state()
        return result

    def heal_loop(self, interval_s=30):
        while True:
            try:
                self.diagnose(heal=True)
            except Exception as exc:
                print(f"auto-heal error: {exc}")
            time.sleep(interval_s)

    def _diagnose(self):
        snap = self.snapshot()
        findings = [f.to_dict() for f in rules.diagnose(snap, self.config.get("thresholds"))]
        self.healer.prune(findings)
        findings = self.healer.escalations() + findings
        plan = runbooks.attach(findings, self.config, snap)
        return {
            "name": snap.get("name"),
            "site": self.config.get("site"),
            "status": rules.overall_status_dicts(findings),
            "preflight": preflight.evaluate(findings),
            "root_causes": rootcause.correlate(findings),
            "plan": plan,
            "findings": findings,
            "snapshot": snap,
        }

    def unit_logs(self, unit, lines=200):
        allowed = set(self.config.get("watch_units", [])) | set(self.config.get("log_units", []))
        if unit not in allowed:
            return None, f"unit not allow-listed: {unit}"
        if self.simulate:
            return f"(simulated) no journal for {unit}\n", None
        if not shutil.which("journalctl"):
            return None, "journalctl not available"
        r = subprocess.run(["journalctl", "-u", unit, "-n", str(min(int(lines), 5000)),
                            "--no-pager", "-o", "short-iso"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout, None


def make_handler(agent):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else (
                body.encode() if isinstance(body, str) else json.dumps(body, default=str).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            token = agent.config.get("token")
            return not token or self.headers.get("Authorization") == f"Bearer {token}"

        def do_GET(self):
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"})
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/health":
                return self._send(200, {"ok": True, "simulated": agent.simulate})
            if url.path == "/snapshot":
                return self._send(200, agent.snapshot())
            if url.path == "/diagnose":
                return self._send(200, agent.diagnose())
            if url.path == "/preflight":
                d = agent.diagnose()
                return self._send(200 if d["preflight"]["decision"] == "GO" else 409,
                                  {"name": d["name"], **d["preflight"]})
            if url.path == "/logs":
                text, err = agent.unit_logs(q.get("unit", [""])[0], q.get("lines", ["200"])[0])
                return self._send(403, {"error": err}) if err else \
                    self._send(200, text, "text/plain; charset=utf-8")
            if url.path == "/actions":
                return self._send(200, agent.runner.catalog())
            if url.path == "/audit":
                return self._send(200, agent.runner.audit_mem[-int(q.get("n", ["50"])[0]):])
            if url.path == "/metrics":
                return self._send(200, metrics.render([agent.diagnose()]),
                                  "text/plain; version=0.0.4")
            if url.path == "/bundle":
                with tempfile.TemporaryDirectory() as tmp:
                    path = bundle.create(agent.diagnose(), tmp,
                                         agent.config.get("bundle_paths", []))
                    with open(path, "rb") as f:
                        data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{os.path.basename(path)}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"})
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/actions/run":
                rec = agent.runner.run_signed(body)
                code = 200 if rec.get("status") in ("done", "failed") else (
                    409 if rec.get("status") == "blocked" else 403)
                return self._send(code, rec)
            if self.path == "/faults" and agent.simulate:
                unknown = set(body.get("faults", [])) - set(sim.FAULTS)
                if unknown:
                    return self._send(400, {"error": f"unknown faults: {sorted(unknown)}"})
                with agent.lock:
                    agent.faults = set(body.get("faults", []))
                return self._send(200, {"faults": sorted(agent.faults)})
            self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            pass

    return Handler


def make_server(agent, host="0.0.0.0", port=8765):
    return ThreadingHTTPServer((host, port), make_handler(agent))


def serve(agent, host="0.0.0.0", port=8765):
    server = make_server(agent, host, port)
    mode = "SIMULATED" if agent.simulate else "live"
    print(f"drone agent ({mode}) listening on http://{host}:{port}")
    server.serve_forever()
