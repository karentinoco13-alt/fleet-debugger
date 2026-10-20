"""Store-and-forward uplink: the vehicle pushes its diagnoses outbound to the console.

Why push instead of poll: remote vehicles sit behind cellular CGNAT/firewalls
and lose connectivity for minutes or hours. The vehicle therefore:

  1. diagnoses itself on a timer whether or not anyone is listening,
  2. appends every result to a bounded on-disk spool (its "black box"),
  3. pushes the spool oldest-first whenever the link is up, deleting only
     what the server acknowledged (at-least-once delivery),
  4. sends a tiny heartbeat every cycle even when nothing changed, so the
     server can tell "healthy and quiet" from "silent".

When bandwidth is scarce, full snapshots are only sent on a status change;
otherwise a compact summary goes out.

Two more paths ride on this connection:
  * Commands: the console's response to an ingest POST may carry signed
    remediation commands queued for this vehicle (its mailbox). They are
    verified and executed locally, and the results go back on the next push.
    No inbound port is needed.
  * Fallback heartbeat: if the main link fails, a ~70-byte P0 heartbeat is
    handed to `fallback_cmd` (an SMS / Iridium SBD / LoRa sender) on stdin, at
    most every `fallback_interval_s`.
"""

import json
import os
import subprocess
import threading
import time
import urllib.request


class Spool:
    """Append-only JSONL queue with a size cap (drops the oldest entries first)."""

    def __init__(self, path, max_bytes=50_000_000):
        self.path, self.max_bytes = path, max_bytes
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def append(self, item):
        line = json.dumps(item, default=str) + "\n"
        with self.lock:
            with open(self.path, "a") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())  # survive power loss on a hard landing
            if os.path.getsize(self.path) > self.max_bytes:
                self._trim()

    def _trim(self):
        with open(self.path) as f:
            lines = f.readlines()
        keep, size = [], 0
        for line in reversed(lines):
            size += len(line)
            if size > self.max_bytes * 0.8:
                break
            keep.append(line)
        self._rewrite(reversed(keep))

    def _rewrite(self, lines):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            f.writelines(lines)
        os.replace(tmp, self.path)

    def peek(self, n):
        with self.lock:
            if not os.path.exists(self.path):
                return []
            with open(self.path) as f:
                return [json.loads(l) for _, l in zip(range(n), f) if l.strip()]

    def drop(self, n):
        with self.lock:
            with open(self.path) as f:
                lines = f.readlines()
            self._rewrite(lines[n:])

    def __len__(self):
        with self.lock:
            if not os.path.exists(self.path):
                return 0
            with open(self.path) as f:
                return sum(1 for _ in f)


def compact(result):
    """Low-bandwidth form: no raw snapshot (~1 KB instead of ~10-50 KB)."""
    return {k: result[k] for k in ("name", "site", "status", "preflight", "root_causes",
                                   "findings", "auto_actions") if k in result}


class Uplink:
    def __init__(self, agent, url, token=None, interval_s=30, spool_path=None,
                 batch=20, full_every_s=600, fallback_cmd=None, fallback_interval_s=300):
        self.agent, self.url, self.token = agent, url.rstrip("/"), token
        self.fallback_cmd, self.fallback_interval_s = fallback_cmd, fallback_interval_s
        self.last_fallback, self.last_result = 0, None
        self.interval_s, self.batch, self.full_every_s = interval_s, batch, full_every_s
        self.spool = Spool(spool_path or "/var/lib/fleetdebug/spool.jsonl")
        self.last_status, self.last_full = None, 0
        self.link_up = None

    def cycle(self):
        result = self.agent.diagnose()
        self.last_result = result
        now = time.time()
        changed = result["status"] != self.last_status
        full = changed or now - self.last_full > self.full_every_s
        item = dict(result) if full else compact(result)
        if full:
            item["actions_catalog"] = self.agent.runner.catalog()
        item.update(ts=now, kind="full" if full else "compact")
        self.spool.append(item)
        self.last_status = result["status"]
        if full:
            self.last_full = now
        self.flush()

    def flush(self):
        while True:
            items = self.spool.peek(self.batch)
            if not items:
                return True
            try:
                req = urllib.request.Request(
                    self.url + "/api/ingest", method="POST",
                    data=json.dumps({"items": items}, default=str).encode(),
                    headers={"Content-Type": "application/json",
                             **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
                with urllib.request.urlopen(req, timeout=10) as r:
                    resp = json.load(r)
                accepted = resp.get("accepted", 0)
                self.spool.drop(accepted)
                self.link_up = True
                for cmd in resp.get("commands", []):
                    rec = self.agent.runner.run_signed(cmd)
                    self.spool.append({"kind": "action_result", "name": self.agent.config.get(
                        "name"), "ts": time.time(), "record": rec, "nonce": cmd.get("nonce")})
                if accepted < len(items):
                    return False
            except Exception as exc:
                if self.link_up is not False:
                    print(f"uplink down ({exc}); spooling locally ({len(self.spool)} queued)")
                self.link_up = False
                self._fallback()
                return False

    def _fallback(self):
        if not self.fallback_cmd or not self.last_result:
            return
        now = time.time()
        if now - self.last_fallback < self.fallback_interval_s:
            return
        from .heartbeat import encode
        line = encode(self.last_result, now)
        try:
            subprocess.run(self.fallback_cmd, input=line + "\n", text=True, timeout=60,
                           check=True, capture_output=True)
            self.last_fallback = now
        except Exception as exc:
            print(f"fallback heartbeat failed: {exc}")

    def run(self):
        while True:
            try:
                self.cycle()
            except Exception as exc:
                print(f"uplink cycle error: {exc}")
            time.sleep(self.interval_s)
