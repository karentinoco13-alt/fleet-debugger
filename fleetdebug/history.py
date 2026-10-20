"""Finding history (SQLite): recurring faults, flapping, and fleet-wide trends.

Fleet operators care less about "is it broken now" than about "which dock
keeps having this problem". Every diagnosis the console sees is stored here.
"""

import json
import sqlite3
import threading
import time


class History:
    def __init__(self, path="fleetdebug_history.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS checks (
                    ts REAL, drone TEXT, status TEXT, decision TEXT);
                CREATE TABLE IF NOT EXISTS findings (
                    ts REAL, drone TEXT, severity TEXT, component TEXT, title TEXT);
                CREATE INDEX IF NOT EXISTS idx_f ON findings(drone, title, ts);
                CREATE TABLE IF NOT EXISTS incidents (
                    ts REAL, drone TEXT, summary TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS dispatches (ts REAL, drone TEXT, decision TEXT);
                CREATE TABLE IF NOT EXISTS actions (
                    ts REAL, drone TEXT, action TEXT, operator TEXT, status TEXT,
                    record TEXT);
            """)

    def record(self, drone, result, ts=None):
        ts = ts or time.time()
        with self.lock:
            self.db.execute("INSERT INTO checks VALUES (?,?,?,?)",
                            (ts, drone, result.get("status"),
                             (result.get("preflight") or {}).get("decision")))
            self.db.executemany(
                "INSERT INTO findings VALUES (?,?,?,?,?)",
                [(ts, drone, f["severity"], f["component"], f["title"])
                 for f in result.get("findings", [])])
            self.db.commit()

    def record_incident(self, drone, summary, payload):
        with self.lock:
            self.db.execute("INSERT INTO incidents VALUES (?,?,?,?)",
                            (time.time(), drone, summary, json.dumps(payload, default=str)))
            self.db.commit()

    def record_action(self, rec):
        with self.lock:
            self.db.execute("INSERT INTO actions VALUES (?,?,?,?,?,?)",
                            (rec.get("ts") or time.time(), rec.get("vehicle"),
                             rec.get("action"), rec.get("operator"), rec.get("status"),
                             json.dumps(rec, default=str)))
            self.db.commit()

    def record_dispatch(self, drone, decision, ts=None):
        with self.lock:
            self.db.execute("INSERT INTO dispatches VALUES (?,?,?)",
                            (ts or time.time(), drone, decision))
            self.db.commit()

    def resolution(self, since_h=168):
        """How problems got resolved: by the vehicle itself, by an operator remotely, or on site."""
        since = time.time() - since_h * 3600
        with self.lock:
            recs = [json.loads(r[0]) for r in self.db.execute(
                "SELECT record FROM actions WHERE ts > ?", (since,)).fetchall()]
            sent = self.db.execute("SELECT COUNT(*) FROM dispatches WHERE ts > ?",
                                   (since,)).fetchone()[0]

        def fixed(r):
            return r.get("status") == "done" and bool((r.get("verify") or {}).get("resolved"))
        auto = sum(1 for r in recs if r.get("operator") == "auto-heal" and fixed(r))
        remote = sum(1 for r in recs if r.get("operator") != "auto-heal" and fixed(r))
        return {"auto": auto, "remote": remote, "technician": sent}

    def actions(self, drone=None, limit=100):
        q = "SELECT record FROM actions {} ORDER BY ts DESC LIMIT ?"
        args = [limit]
        if drone:
            q, args = q.format("WHERE drone = ?"), [drone, limit]
        else:
            q = q.format("")
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute(q, args).fetchall()]

    def recurring(self, drone=None, since_h=168, limit=20):
        """The most frequent findings: these are your maintenance backlog."""
        q = """SELECT drone, component, title, severity, COUNT(*) n,
                      MIN(ts) first, MAX(ts) last
               FROM findings WHERE ts > ? {} GROUP BY drone, title
               ORDER BY n DESC LIMIT ?"""
        args = [time.time() - since_h * 3600]
        if drone:
            q = q.format("AND drone = ?")
            args.append(drone)
        else:
            q = q.format("")
        args.append(limit)
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        return [dict(zip(("drone", "component", "title", "severity", "count",
                          "first_seen", "last_seen"), r)) for r in rows]

    def availability(self, since_h=168):
        """Share of checks per drone where the preflight decision was GO."""
        with self.lock:
            rows = self.db.execute(
                """SELECT drone, COUNT(*),
                          SUM(CASE WHEN decision='GO' THEN 1 ELSE 0 END)
                   FROM checks WHERE ts > ? GROUP BY drone""",
                (time.time() - since_h * 3600,)).fetchall()
        return {d: round(100.0 * go / n, 1) if n else None for d, n, go in rows}

    def by_component(self, since_h=168):
        with self.lock:
            rows = self.db.execute(
                """SELECT component, COUNT(*) FROM findings WHERE ts > ?
                   GROUP BY component ORDER BY 2 DESC""",
                (time.time() - since_h * 3600,)).fetchall()
        return dict(rows)
