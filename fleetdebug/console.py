"""Ground/NOC console: fleet state, history, alerts, remote actions and the dashboard API.

Vehicles report in two ways (mixable in one fleet):
  pull  - the console polls the agent's /diagnose (LAN / VPN)
  push  - the vehicle POSTs to /api/ingest (cellular / CGNAT), and receives
          queued commands in the response (its mailbox)
plus /api/heartbeat for P0 lines relayed by an SMS/satellite gateway.

Access control: if `users` is configured, every dashboard/API call needs HTTP
Basic auth, and the authenticated username is what goes into the action audit
log. Vehicle-facing endpoints (/api/ingest, /api/heartbeat) use `ingest_token`.
"""

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from . import actions, dispatch, fleetcorr, heartbeat, logs, metrics, runbooks, sim
from .history import History
from .integrations import Notifier

STATIC = os.path.join(os.path.dirname(__file__), "static")


def hash_password(password, salt=None):
    salt = salt or os.urandom(8).hex()
    return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"


def check_password(stored, password):
    salt, _, digest = stored.partition("$")
    return hmac.compare_digest(hash_password(password, salt), stored)


def _request(drone, path, timeout=5, data=None):
    req = urllib.request.Request(drone["url"].rstrip("/") + path, data=data,
                                 method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if drone.get("token"):
        req.add_header("Authorization", f"Bearer {drone['token']}")
    return urllib.request.urlopen(req, timeout=timeout)


def fetch(drone, timeout=5):
    try:
        with _request(drone, "/diagnose", timeout) as r:
            data = json.load(r)
    except Exception as exc:
        res = {"name": drone.get("name", drone["url"]), "url": drone["url"],
                "site": drone.get("site"), "status": "unreachable", "error": str(exc),
                "preflight": {"decision": "NO-GO", "blockers": ["Agent unreachable"],
                              "holds": [], "advisories": []},
                "root_causes": [],
                "findings": [{"severity": "critical", "component": "link",
                              "title": "Agent unreachable", "detail": str(exc),
                              "fix": "Check the vehicle and its base station are powered, the agent service is "
                                     "running (`systemctl status fleetdebug-agent`) and the "
                                     "VPN/LTE route to it."}]}
        res["plan"] = runbooks.attach(res["findings"], {})
        return res
    data["url"] = drone["url"]
    data["name"] = drone.get("name") or data.get("name")
    data["site"] = drone.get("site") or data.get("site")
    return data


class Fleet:
    def __init__(self, drones, history_path, notify, interval, silent_after_s=120,
                 ingest_token=None, command_ttl_s=300, dispatch_policy=None):
        self.drones = drones
        self.silent_after_s = silent_after_s
        self.ingest_token = ingest_token
        self.command_ttl_s = command_ttl_s
        self.history = History(history_path)
        self.notifier = Notifier(notify)
        self.interval = interval
        self.latest = {}
        self.mailbox = {}  # vehicle name -> [signed command envelopes]
        self.first_seen = {}  # vehicle name -> {finding key: ts it started}
        self.auto_seen = {}  # vehicle name -> ts of the newest self-heal record stored
        self.last_decision = {}  # vehicle name -> last dispatch decision
        self.dispatch_policy = dispatch_policy
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=16)

    # ------------------------------------------------------------ state
    def poll_once(self):
        pull = [d for d in self.drones if d.get("url")]
        for res in self.pool.map(fetch, pull):
            res["mode"] = "pull"
            self._store(res, time.time())

    def _store(self, res, ts):
        with self.lock:
            prev = self.latest.get(res["name"], {})
            if res.get("kind") in ("compact", "heartbeat"):
                for k in ("snapshot", "actions_catalog"):
                    if prev.get(k) and not res.get(k):
                        res[k] = prev[k]  # keep the last full snapshot for display
                if res.get("kind") == "heartbeat":
                    res["site"] = res.get("site") or prev.get("site")
            if ts < prev.get("last_seen", 0):
                # Backfilled report older than what we have: history only.
                self.history.record(res["name"], res, ts)
                return
            self.latest[res["name"]] = {**res, "last_seen": ts}
            if res.get("kind") != "heartbeat":
                seen = self.first_seen.setdefault(res["name"], {})
                keys = {f.get("key") for f in res.get("findings", []) if f.get("key")}
                for k in keys:
                    seen.setdefault(k, ts)
                for k in set(seen) - keys:
                    del seen[k]  # cleared: if it comes back, the clock restarts
        self.history.record(res["name"], res, ts)
        for a in res.get("auto_actions") or []:
            if a.get("ts", 0) > self.auto_seen.get(res["name"], 0):
                self.history.record_action({**a, "via": "self-heal"})
                self.auto_seen[res["name"]] = a["ts"]
        self.notifier.handle(res)

    def ingest(self, items):
        """Batches pushed by vehicle uplinks; may include hours of backlog."""
        n, names = 0, set()
        for item in sorted(items, key=lambda i: i.get("ts", 0)):
            name = item.get("name")
            if not name:
                continue
            names.add(name)
            n += 1
            if item.get("kind") == "action_result":
                self.history.record_action({**item["record"], "via": "mailbox"})
                continue
            item["mode"] = "push"
            item["backlog"] = time.time() - item.get("ts", time.time()) > 60
            self._store(item, item.get("ts", time.time()))
        with self.lock:
            commands = [c for name in names for c in self.mailbox.pop(name, [])
                        if c["expires"] > time.time()]
        return n, commands

    def ingest_heartbeat(self, line):
        hb = heartbeat.decode(line)
        hb["mode"] = "push"
        self._store(hb, hb["ts"])
        return hb["name"]

    def view(self):
        """Latest state per vehicle; vehicles that have gone quiet are marked SILENT."""
        now = time.time()
        out = []
        with self.lock:
            latest = list(self.latest.values())
        for d in latest:
            d = dict(d)
            age = now - d.get("last_seen", now)
            d["age_s"] = round(age, 1)
            d["pending_commands"] = len(self.mailbox.get(d["name"], []))
            if d.get("mode") == "push" and age > self.silent_after_s:
                d["status"] = "unreachable"
                d["preflight"] = {"decision": "NO-GO", "blockers": ["Vehicle silent"],
                                  "holds": [], "advisories": []}
                silent = [{"severity": "critical", "component": "link",
                                  "title": f"No heartbeat for {int(age)}s",
                                  "detail": "Last known state is shown below. The vehicle "
                                            "keeps spooling locally and will backfill on "
                                            "reconnect.",
                                  "fix": "Check carrier coverage/outage at the site, modem "
                                         "health on the last report, and base station power."}]
                runbooks.attach(silent, {})
                d["findings"] = silent + d.get("findings", [])
                d["plan"] = {"remote": 0, "wait": 1, "site": 0,
                             "next": "Wait for the vehicle to reconnect; check the carrier and "
                                     "base station power if it stays silent."}
            fs = dict(self.first_seen.get(d["name"], {}))
            for f in d.get("findings", []):
                if f.get("key") and f["key"] not in fs:
                    # Silent vehicles: the outage started when it last reported.
                    fs[f["key"]] = d.get("last_seen", now)
            d["dispatch"] = dispatch.decide(d, fs, self.history.actions(d["name"], 200),
                                            self.dispatch_policy, now)
            dec = d["dispatch"]["decision"]
            if dec.startswith("dispatch") and not self.last_decision.get(
                    d["name"], "").startswith("dispatch"):
                self.history.record_dispatch(d["name"], dec, now)
            self.last_decision[d["name"]] = dec
            out.append(d)
        return sorted(out, key=lambda d: d["name"])

    def run(self):
        while True:
            try:
                self.poll_once()
            except Exception as exc:
                print(f"poll error: {exc}")
            time.sleep(self.interval)

    def drone(self, key):
        return next((d for d in self.drones if key in (d.get("name"), d.get("url"))), None)

    # ------------------------------------------------------------ actions
    def catalog(self, key):
        d = self.drone(key)
        if d and d.get("url"):
            with _request(d, "/actions") as r:
                return json.load(r)
        cached = (self.latest.get(key) or {}).get("actions_catalog")
        if cached:
            return {**cached, "cached": True}
        return {"enabled": False, "actions": [], "error": "no catalog reported yet"}

    def send_action(self, key, action, params, operator, ticket="", reason=""):
        d = self.drone(key)
        if not d:
            return 404, {"error": "unknown vehicle"}
        if not d.get("action_secret"):
            return 400, {"error": "no action_secret configured for this vehicle"}
        env = actions.make_command(action, params, d["action_secret"], operator, ticket,
                                   reason, self.command_ttl_s)
        if d.get("url"):
            try:
                with _request(d, "/actions/run", timeout=90,
                              data=json.dumps(env).encode()) as r:
                    rec = json.load(r)
            except urllib.error.HTTPError as e:
                rec = json.loads(e.read() or b"{}")
            except Exception as exc:
                rec = {"ok": False, "status": "unreachable", "error": str(exc),
                       "action": action, "operator": operator}
            rec["via"] = "direct"
            self.history.record_action(rec)
            threading.Thread(target=self.poll_once, daemon=True).start()
            return 200, rec
        with self.lock:
            self.mailbox.setdefault(d["name"], []).append(env)
        rec = {"ts": time.time(), "vehicle": d["name"], "action": action, "params": params,
               "operator": operator, "ticket": ticket, "reason": reason, "status": "queued",
               "via": "mailbox", "expires": env["expires"]}
        self.history.record_action(rec)
        return 202, rec


def _parse_csv(text):
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        row = {}
        for k, v in r.items():
            try:
                row[k] = float(v)
            except (TypeError, ValueError):
                row[k] = v
        rows.append(row)
    return rows


def make_handler(fleet, users=None, metrics_public=False):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else (
                body.encode() if isinstance(body, str) else json.dumps(body, default=str).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _user(self):
            """Returns the username, 'anonymous' when auth is off, or None if denied."""
            if not users:
                return "anonymous"
            h = self.headers.get("Authorization", "")
            if h.startswith("Basic "):
                try:
                    name, _, pw = base64.b64decode(h[6:]).decode().partition(":")
                except Exception:
                    return None
                if name in users and check_password(users[name], pw):
                    return name
            return None

        def _deny(self):
            self._send(401, {"error": "login required"}, extra={
                "WWW-Authenticate": 'Basic realm="fleetdebug"'})

        def _vehicle_auth(self):
            tok = fleet.ingest_token
            return not tok or self.headers.get("Authorization") == f"Bearer {tok}"

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/metrics" and metrics_public:
                return self._send(200, metrics.render(fleet.view()), "text/plain; version=0.0.4")
            user = self._user()
            if not user:
                return self._deny()
            if url.path in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if url.path == "/metrics":
                return self._send(200, metrics.render(fleet.view()), "text/plain; version=0.0.4")
            if url.path == "/api/me":
                return self._send(200, {"user": user, "auth": bool(users)})
            if url.path == "/api/fleet":
                if q.get("refresh"):
                    fleet.poll_once()
                return self._send(200, fleet.view())
            if url.path == "/api/incidents":
                return self._send(200, fleetcorr.correlate(fleet.view()))
            if url.path == "/api/history":
                hours = float(q.get("hours", 168))
                return self._send(200, {
                    "recurring": fleet.history.recurring(q.get("drone"), hours),
                    "availability": fleet.history.availability(hours),
                    "by_component": fleet.history.by_component(hours),
                    "resolution": fleet.history.resolution(hours),
                    "policy": {**dispatch.DEFAULT_POLICY, **(fleet.dispatch_policy or {})},
                })
            if url.path == "/api/audit":
                return self._send(200, fleet.history.actions(q.get("drone"),
                                                             int(q.get("limit", 100))))
            if url.path == "/api/faults":
                return self._send(200, sim.FAULTS)
            if url.path == "/api/actions":
                try:
                    return self._send(200, fleet.catalog(q.get("drone", "")))
                except Exception as exc:
                    return self._send(502, {"error": str(exc)})
            d = fleet.drone(q.get("drone", ""))
            if url.path in ("/api/logs", "/api/bundle") and d and not d.get("url"):
                return self._send(409, {"error": "push-only vehicle: use the remote-access "
                                                 "tunnel, or a bundle action"})
            if url.path == "/api/logs" and d:
                try:
                    with _request(d, f"/logs?unit={quote(q.get('unit', ''))}&lines="
                                     f"{int(q.get('lines', 200))}") as r:
                        return self._send(200, r.read(), "text/plain; charset=utf-8")
                except urllib.error.HTTPError as e:
                    return self._send(e.code, e.read())
                except Exception as exc:
                    return self._send(502, {"error": str(exc)})
            if url.path == "/api/bundle" and d:
                try:
                    with _request(d, "/bundle", timeout=60) as r:
                        return self._send(200, r.read(), "application/gzip", {
                            "Content-Disposition": r.headers.get("Content-Disposition", "")})
                except Exception as exc:
                    return self._send(502, {"error": str(exc)})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            if self.path in ("/api/ingest", "/api/heartbeat"):
                if not self._vehicle_auth():
                    return self._send(401, {"error": "unauthorized"})
                if self.path == "/api/ingest":
                    n, commands = fleet.ingest(json.loads(body or b"{}").get("items", []))
                    return self._send(200, {"accepted": n, "commands": commands})
                ok, bad = [], []
                for line in body.decode(errors="replace").splitlines():
                    if line.strip():
                        try:
                            ok.append(fleet.ingest_heartbeat(line))
                        except (ValueError, KeyError, IndexError) as exc:
                            bad.append(str(exc))
                return self._send(200 if not bad else 400, {"accepted": ok, "errors": bad})
            user = self._user()
            if not user:
                return self._deny()
            if self.path == "/api/analyze-log":
                rows = _parse_csv(body.decode(errors="replace"))
                if rows and "time_s" not in rows[0]:
                    return self._send(400, {"error": "CSV needs a time_s column"})
                return self._send(200, logs.analyze(rows))
            req = json.loads(body or b"{}")
            if self.path == "/api/action":
                operator = user if users else (req.get("operator") or "anonymous")
                code, rec = fleet.send_action(req.get("drone", ""), req.get("action", ""),
                                              req.get("params") or {}, operator,
                                              req.get("ticket", ""), req.get("reason", ""))
                return self._send(code, rec)
            if self.path == "/api/faults":
                d = fleet.drone(req.get("drone", ""))
                if not d or not d.get("url"):
                    return self._send(404, {"error": "unknown or push-only vehicle"})
                try:
                    with _request(d, "/faults",
                                  data=json.dumps({"faults": req.get("faults", [])}).encode()) as r:
                        res = json.load(r)
                    fleet.poll_once()
                    return self._send(200, res)
                except Exception as exc:
                    return self._send(502, {"error": str(exc)})
            self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            pass

    return Handler


def serve(config, host="0.0.0.0", port=8080):
    fleet = Fleet(config.get("drones", []), config.get("history_db", "fleetdebug_history.db"),
                  config.get("notify", []), config.get("poll_interval_s", 10),
                  config.get("silent_after_s", 120), config.get("ingest_token"),
                  config.get("command_ttl_s", 300), config.get("dispatch_policy"))
    threading.Thread(target=fleet.run, daemon=True).start()
    users = config.get("users")
    if not users and host not in ("127.0.0.1", "localhost"):
        print("WARNING: no `users` configured: the console (and remote actions) are open "
              "to anyone who can reach this port.")
    server = ThreadingHTTPServer((host, port), make_handler(fleet, users,
                                                            config.get("metrics_public", False)))
    print(f"fleet console on http://{host}:{port}  ({len(fleet.drones)} vehicle(s))")
    server.serve_forever()
