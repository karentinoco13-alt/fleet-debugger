import json
import os
import tempfile
import threading
import unittest
import urllib.request

from fleetdebug import agent, console, logs, preflight, rootcause, rules, sim
from fleetdebug.uplink import Spool, Uplink


def diag(*faults):
    return agent.Agent({"name": "t"}, simulate=True, faults=faults).diagnose()


class RulesTest(unittest.TestCase):
    def test_healthy_sim_is_go(self):
        d = diag()
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["preflight"]["decision"], "GO")

    def test_every_fault_is_detected(self):
        for fault in sim.FAULTS:
            with self.subTest(fault=fault):
                self.assertNotEqual(diag(fault)["status"], "ok")

    def test_weather_is_hold_not_nogo(self):
        self.assertEqual(diag("high_wind")["preflight"]["decision"], "HOLD")

    def test_parachute_blocks_launch(self):
        self.assertEqual(diag("parachute")["preflight"]["decision"], "NO-GO")

    def test_rule_crash_is_contained(self):
        snap = sim.snapshot()
        snap["telemetry"]["vibration"] = "garbage"
        rules.diagnose(snap)  # must not raise


class RootCauseTest(unittest.TestCase):
    def test_gps_cluster(self):
        causes = [r["cause"] for r in diag("gps_loss")["root_causes"]]
        self.assertTrue(any("GNSS" in c for c in causes))

    def test_software_cluster(self):
        causes = [r["cause"] for r in diag("crashed_node", "oom")["root_causes"]]
        self.assertTrue(any("Python" in c for c in causes))


class LogTest(unittest.TestCase):
    def test_failsafe_is_explained(self):
        report = logs.analyze(sim.flight_log_rows(faults=("gps_loss",)))
        fs = [m for m in report["timeline"] if m["critical"]]
        self.assertTrue(fs)
        self.assertIn("GPS satellite count dropped", fs[0]["preceded_by"])

    def test_battery_sag(self):
        report = logs.analyze(sim.flight_log_rows(faults=("battery_sag",)))
        self.assertTrue(any(e["title"] == "Battery voltage sag" for e in report["events"]))


class StoreAndForwardTest(unittest.TestCase):
    def test_spool_survives_outage_then_backfills(self):
        tmp = tempfile.mkdtemp()
        a = agent.Agent({"name": "rover"}, simulate=True)
        up = Uplink(a, "http://127.0.0.1:1", spool_path=os.path.join(tmp, "s.jsonl"))
        for _ in range(3):
            up.cycle()  # console down: everything spools
        self.assertEqual(len(up.spool), 3)

        fleet = console.Fleet([], ":memory:", [], 999)
        srv = console.ThreadingHTTPServer(("127.0.0.1", 0), console.make_handler(fleet))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        up.url = f"http://127.0.0.1:{srv.server_address[1]}"
        self.assertTrue(up.flush())
        self.assertEqual(len(up.spool), 0)
        self.assertEqual(fleet.view()[0]["name"], "rover")
        srv.shutdown()

    def test_spool_cap(self):
        s = Spool(os.path.join(tempfile.mkdtemp(), "s.jsonl"), max_bytes=2000)
        for i in range(200):
            s.append({"i": i, "pad": "x" * 50})
        self.assertLess(os.path.getsize(s.path), 2000)
        self.assertEqual(s.peek(1000)[-1]["i"], 199)  # newest kept

    def test_silent_vehicle_is_nogo(self):
        fleet = console.Fleet([], ":memory:", [], 999, silent_after_s=10)
        item = {**diag(), "ts": 0}
        fleet.ingest([item])
        v = fleet.view()[0]
        self.assertEqual(v["preflight"]["decision"], "NO-GO")


class AgentHttpTest(unittest.TestCase):
    def test_endpoints_and_auth(self):
        a = agent.Agent({"name": "h", "token": "s3cret", "watch_units": ["x.service"]},
                        simulate=True)
        srv = agent.make_server(a, "127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/diagnose")
        self.assertEqual(e.exception.code, 401)
        req = urllib.request.Request(base + "/diagnose",
                                     headers={"Authorization": "Bearer s3cret"})
        self.assertEqual(json.load(urllib.request.urlopen(req))["status"], "ok")
        req = urllib.request.Request(base + "/logs?unit=sshd.service",
                                     headers={"Authorization": "Bearer s3cret"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 403)  # not allow-listed
        srv.shutdown()


class LiveCollectorsTest(unittest.TestCase):
    def test_live_collection_on_this_host(self):
        d = agent.Agent({"name": "live", "watch_processes": ["python"]}).diagnose()
        self.assertIn(d["status"], ("ok", "warning", "critical"))
        self.assertIn("percent", d["snapshot"]["cpu"])


if __name__ == "__main__":
    unittest.main()
