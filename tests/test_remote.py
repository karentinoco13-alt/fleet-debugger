import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from fleetdebug import actions, agent, console, fleetcorr, heartbeat, metrics
from fleetdebug.uplink import Uplink

SECRET = "s3cret"


def mk(name="v1", faults=(), **cfg):
    return agent.Agent({"name": name, "action_secret": SECRET,
                        "watch_units": ["mission.service"], **cfg},
                       simulate=True, faults=faults)


class SigningTest(unittest.TestCase):
    def setUp(self):
        self.a = mk(faults=["crashed_node"])

    def test_valid_command_runs_and_verifies(self):
        env = actions.make_command("restart_service", {"unit": "mission.service"}, SECRET, "op")
        rec = self.a.runner.run_signed(env)
        self.assertEqual(rec["status"], "done")
        self.assertIn("Process 'mission_node.py' is not running", rec["verify"]["resolved"])

    def test_tampered_command_rejected(self):
        env = actions.make_command("restart_service", {"unit": "mission.service"}, SECRET, "op")
        env["action"] = "reboot"
        self.assertEqual(self.a.runner.run_signed(env)["error"], "bad signature")

    def test_wrong_secret_rejected(self):
        env = actions.make_command("reboot", {}, "other", "op")
        self.assertEqual(self.a.runner.run_signed(env)["error"], "bad signature")

    def test_expired_command_rejected(self):
        env = actions.make_command("vacuum_journal", {}, SECRET, "op", ttl_s=-1)
        self.assertIn("expired", self.a.runner.run_signed(env)["error"])

    def test_replay_rejected(self):
        env = actions.make_command("vacuum_journal", {}, SECRET, "op")
        self.assertEqual(self.a.runner.run_signed(env)["status"], "done")
        self.assertEqual(self.a.runner.run_signed(env)["error"], "replayed command")

    def test_no_secret_disables_actions(self):
        a = agent.Agent({"name": "x"}, simulate=True)
        env = actions.make_command("vacuum_journal", {}, SECRET, "op")
        self.assertIn("disabled", a.runner.run_signed(env)["error"])

    def test_unlisted_unit_refused(self):
        env = actions.make_command("restart_service", {"unit": "sshd.service"}, SECRET, "op")
        self.assertEqual(self.a.runner.run_signed(env)["status"], "failed")


class PreconditionTest(unittest.TestCase):
    def test_armed_vehicle_blocks_action(self):
        a = mk()
        orig = a.snapshot

        def armed():
            s = orig()
            s["telemetry"]["armed"] = True
            return s
        a.snapshot = armed
        rec = a.runner.execute("restart_service", {"unit": "mission.service"}, "op")
        self.assertEqual(rec["status"], "blocked")

    def test_unknown_state_blocks(self):
        a = agent.Agent({"name": "live", "action_secret": SECRET,  # real host, no FC
                         "audit_path": os.path.join(tempfile.mkdtemp(), "audit.jsonl")})
        rec = a.runner.execute("reboot", {}, "op")
        self.assertEqual(rec["status"], "blocked")

    def test_skip_precondition_for_rover(self):
        a = mk(skip_preconditions=["docked"])
        ok, pre = a.runner.check_preconditions(["docked"], a.snapshot())
        self.assertTrue(ok)


class AutoHealTest(unittest.TestCase):
    def test_heals_then_escalates_when_fix_does_not_stick(self):
        a = mk(faults=["crashed_node"], auto_remediate=[{
            "match": "Process 'mission_node.py' is not running", "action": "restart_service",
            "params": {"unit": "mission.service"}, "max_per_hour": 2}], heal_step_wait_s=0)
        r = a.diagnose(heal=True)
        self.assertEqual(r["auto_actions"][0]["status"], "done")
        self.assertNotIn("crashed_node", a.faults)
        # The fault keeps coming back: after max_per_hour runs, escalate to a human.
        for _ in range(3):
            a.faults.add("crashed_node")
            r = a.diagnose(heal=True)
        self.assertTrue(any(f["title"].startswith("Automatic fixes used up")
                            for f in r["findings"]))


class MailboxTest(unittest.TestCase):
    def test_command_reaches_push_vehicle_via_ingest_response(self):
        fleet = console.Fleet([{"name": "rover", "action_secret": SECRET}], ":memory:", [], 999)
        srv = console.ThreadingHTTPServer(("127.0.0.1", 0), console.make_handler(fleet))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        a = mk("rover", faults=["crashed_node"])
        up = Uplink(a, f"http://127.0.0.1:{srv.server_address[1]}",
                    spool_path=os.path.join(tempfile.mkdtemp(), "s.jsonl"))
        up.cycle()
        code, rec = fleet.send_action("rover", "restart_service", {"unit": "mission.service"},
                                      "op", "T-1")
        self.assertEqual((code, rec["status"]), (202, "queued"))
        up.cycle()  # picks up the command and runs it
        up.cycle()  # reports the result
        audit = fleet.history.actions("rover")
        self.assertTrue(any(r["status"] == "done" for r in audit))
        self.assertNotIn("crashed_node", a.faults)
        srv.shutdown()

    def test_expired_mailbox_commands_are_dropped(self):
        fleet = console.Fleet([{"name": "rover", "action_secret": SECRET}], ":memory:", [], 999,
                              command_ttl_s=-1)
        fleet.send_action("rover", "vacuum_journal", {}, "op")
        _, cmds = fleet.ingest([{"name": "rover", "ts": time.time(), "status": "ok",
                                 "findings": []}])
        self.assertEqual(cmds, [])


class ConsoleAuthTest(unittest.TestCase):
    def test_basic_auth_and_operator_identity(self):
        users = {"karen": console.hash_password("pw")}
        fleet = console.Fleet([], ":memory:", [], 999)
        srv = console.ThreadingHTTPServer(("127.0.0.1", 0), console.make_handler(fleet, users))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/fleet")
        self.assertEqual(e.exception.code, 401)
        import base64
        req = urllib.request.Request(base + "/api/me", headers={
            "Authorization": "Basic " + base64.b64encode(b"karen:pw").decode()})
        self.assertEqual(json.load(urllib.request.urlopen(req))["user"], "karen")
        srv.shutdown()


class FleetCorrelationTest(unittest.TestCase):
    def test_site_and_version_patterns(self):
        res = []
        for n, site, f, ver in (("a", "S1", ["gps_loss"], "1"), ("b", "S1", ["gps_loss"], "1"),
                                ("c", "S2", ["crashed_node"], "2"),
                                ("d", "S3", ["crashed_node"], "2"), ("e", "S2", [], "1")):
            a = mk(n, faults=f, site=site)
            a.sim_version = ver
            res.append(a.diagnose())
        inc = fleetcorr.correlate(res)
        self.assertTrue(any(i["scope"] == "site" and i["group"] == "S1"
                            and i["signature"] == "gnss" for i in inc))
        self.assertTrue(any(i["scope"] == "software version" and i["group"] == "2"
                            for i in inc))
        self.assertFalse(any(i["scope"] == "site" and i["group"] == "S2" for i in inc))


class HeartbeatTest(unittest.TestCase):
    def test_roundtrip_fits_sms(self):
        r = mk(faults=["fc_link", "gps_loss", "low_battery", "parachute"]).diagnose()
        line = heartbeat.encode(r, 1792464902)
        self.assertLessEqual(len(line), 160)
        d = heartbeat.decode(line)
        self.assertEqual(d["preflight"]["decision"], "NO-GO")
        self.assertTrue(d["findings"])

    def test_corruption_detected(self):
        line = heartbeat.encode(mk().diagnose(), 1)
        with self.assertRaises(ValueError):
            heartbeat.decode(line.replace("|o|", "|c|"))


class MetricsTest(unittest.TestCase):
    def test_prometheus_format(self):
        text = metrics.render([mk(faults=["vibration"]).diagnose()])
        self.assertIn('fleetdebug_status{vehicle="v1"', text)
        self.assertIn("fleetdebug_vibration_max", text)


if __name__ == "__main__":
    unittest.main()


class RunbookTest(unittest.TestCase):
    def test_every_simulated_fault_has_a_route(self):
        from fleetdebug import sim
        for fault in sim.FAULTS:
            r = mk(faults=[fault], watch_units=["mission.service", "perception.service",
                                                "uploader.service"]).diagnose()
            for f in r["findings"]:
                self.assertIn(f["runbook"]["route"], ("remote", "wait", "site"), f["title"])
                self.assertTrue(f["runbook"]["steps"])

    def test_crashed_node_gets_one_click_fix_that_works(self):
        a = mk(faults=["crashed_node"])
        f = next(x for x in a.diagnose()["findings"] if "not running" in x["title"])
        act = f["runbook"]["action"]
        self.assertEqual(act["params"], {"unit": "mission.service"})
        rec = a.runner.execute(act["name"], act["params"], "op")
        self.assertIn(f["title"], rec["verify"]["resolved"])

    def test_gps_sensor_alert_is_wait_not_site(self):
        r = mk(faults=["gps_loss"]).diagnose()
        f = next(x for x in r["findings"] if x["title"] == "FC reports unhealthy sensors")
        self.assertEqual(f["runbook"]["route"], "wait")

    def test_remote_route_requires_available_action(self):
        r = agent.Agent({"name": "x"}, simulate=True, faults=["upload_backlog"]).diagnose()
        f = next(x for x in r["findings"] if x["component"] == "data-pipeline")
        self.assertEqual(f["runbook"]["route"], "site")  # uploader.service not watched
