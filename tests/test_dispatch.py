import time
import unittest

from fleetdebug import agent, dispatch


def diag(faults, **cfg):
    a = agent.Agent({"name": "v", "watch_units": ["mission.service", "uploader.service",
                                                  "perception.service"],
                     "auto_remediate": [], **cfg}, simulate=True, faults=faults)
    return a, a.diagnose()


def ages(result, hours):
    now = time.time()
    return {f["key"]: now - hours * 3600 for f in result["findings"]}


class DispatchPolicyTest(unittest.TestCase):
    def test_healthy_needs_nothing(self):
        _, r = diag([])
        self.assertEqual(dispatch.decide(r, {}, [])["decision"], "ok")

    def test_physical_critical_dispatches_now_with_work_order(self):
        _, r = diag(["lid_jam"])
        d = dispatch.decide(r, ages(r, 0.1), [])
        self.assertEqual(d["decision"], "dispatch-now")
        self.assertIn("Spare limit switch", d["work_order"])
        self.assertIn("Nothing: no remote fix exists", d["work_order"])

    def test_remote_fix_must_be_tried_before_dispatch(self):
        _, r = diag(["fc_link"])
        # A lost FC link has a remote fix (reboot): try it before sending anyone.
        self.assertEqual(dispatch.decide(r, ages(r, 0.1), [])["decision"], "try-remote")
        items = {i["title"]: i for i in dispatch.decide(r, ages(r, 0.1), [])["items"]}
        self.assertEqual(items["Flight controller heartbeat lost"]["decision"], "try-remote")

    def test_after_max_attempts_dispatch(self):
        a, r = diag(["thermal_cam"])
        f = next(x for x in r["findings"] if x["runbook"].get("action"))
        act = f["runbook"]["action"]
        since = time.time() - 3600
        audit = [{"action": act["name"], "params": act["params"], "status": "done",
                  "ts": since + 60 * k, "operator": "op"} for k in range(2)]
        d = dispatch.decide(r, {x["key"]: since for x in r["findings"]}, audit)
        self.assertEqual(d["decision"], "dispatch-now")
        self.assertIn("ALREADY TRIED REMOTELY", d["work_order"])
        self.assertIn("problem came back", d["work_order"])

    def test_old_attempts_before_problem_started_do_not_count(self):
        _, r = diag(["upload_backlog"])
        f = next(x for x in r["findings"] if x["component"] == "data-pipeline")
        act = f["runbook"]["action"]
        audit = [{"action": act["name"], "params": act["params"], "status": "done",
                  "ts": time.time() - 86400, "operator": "op"}] * 2
        d = dispatch.decide(r, ages(r, 1), audit)
        self.assertEqual(d["decision"], "try-remote")

    def test_wait_until_limit_then_dispatch(self):
        _, r = diag(["gps_loss"])
        self.assertEqual(dispatch.decide(r, ages(r, 0.5), [])["decision"], "wait")
        self.assertEqual(dispatch.decide(r, ages(r, 3), [])["decision"], "dispatch-now")

    def test_weather_never_dispatches(self):
        _, r = diag(["high_wind"])
        self.assertEqual(dispatch.decide(r, ages(r, 100), [])["decision"], "wait")

    def test_thresholds_are_configurable(self):
        _, r = diag(["gps_loss"])
        d = dispatch.decide(r, ages(r, 3), [], {"wait_limit_h": {"gps": 6, "estimator": 6,
                                                                  "flight-controller": 6}})
        self.assertEqual(d["decision"], "wait")

    def test_physical_warning_is_scheduled_not_urgent(self):
        _, r = diag([])
        r["findings"] = [{"severity": "warning", "component": "dock", "title": "Dock humidity 90%",
                          "detail": "", "fix": "", "key": "k",
                          "runbook": {"route": "site", "steps": ["x"], "bring": [], "verify": ""}}]
        self.assertEqual(dispatch.decide(r, {}, [])["decision"], "dispatch-scheduled")


class SelfHealingPreventsDispatchTest(unittest.TestCase):
    CONNECTIVITY_AND_PEOPLE_ERRORS = ["vpn_down", "dns_fail", "modem_hung", "sim_no_service",
                                      "clock_skew", "config_drift", "service_disabled",
                                      "geofence_missing", "disk_full", "crashed_node", "oom",
                                      "upload_backlog"]

    def test_common_faults_fix_themselves_without_dispatch(self):
        for fault in self.CONNECTIVITY_AND_PEOPLE_ERRORS:
            with self.subTest(fault=fault):
                a = agent.Agent({"name": "v", "watch_units": ["mission.service",
                                 "uploader.service", "perception.service"],
                                 "heal_step_wait_s": 0}, simulate=True, faults=[fault])
                for _ in range(6):
                    a.diagnose(heal=True)
                r = a.diagnose()
                self.assertEqual(r["status"], "ok", r["findings"])

    def test_while_healing_the_decision_is_auto_fixing(self):
        a = agent.Agent({"name": "v", "heal_step_wait_s": 3600}, simulate=True,
                        faults=["modem_hung"])
        a.diagnose(heal=True)  # first ladder step runs, then waits
        r = a.diagnose()
        d = dispatch.decide(r, ages(r, 0.1), [])
        self.assertEqual(d["decision"], "auto-fixing")

    def test_hardware_link_fault_escalates_to_dispatch_after_ladder(self):
        a = agent.Agent({"name": "v", "heal_step_wait_s": 0}, simulate=True,
                        faults=["cellular_weak"])
        for _ in range(4):
            a.diagnose(heal=True)
        r = a.diagnose()
        d = dispatch.decide(r, ages(r, 0.2), [])
        self.assertEqual(d["decision"], "dispatch-now")
        self.assertIn("Spare LTE antenna", d["work_order"])

    def test_software_regression_rolls_back_instead_of_dispatch(self):
        a = agent.Agent({"name": "v", "watch_units": ["mission.service"],
                         "heal_step_wait_s": 0}, simulate=True, faults=["crashed_node"])
        a.sim_version = "2.5.0-rc1"
        for _ in range(8):  # the crash keeps coming back after each restart
            a.faults.add("crashed_node")
            a.diagnose(heal=True)
        a.faults.add("crashed_node")
        r = a.diagnose()
        d = dispatch.decide(r, ages(r, 0.2), [])
        esc = next(i for i in d["items"] if i["title"].startswith("Automatic fixes used up"))
        self.assertEqual(esc["action"]["name"], "rollback_software")
        self.assertEqual(d["decision"], "try-remote")


if __name__ == "__main__":
    unittest.main()
