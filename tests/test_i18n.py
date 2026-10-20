"""Every message the engine can show must have a Spanish translation in static/i18n.js.

Runs the translator in Node (skipped when Node isn't installed) over the text
the engine produces for every simulated fault, before and after self-healing,
including decisions and work orders.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from fleetdebug import agent, dispatch, fleetcorr, logs, rootcause, runbooks, sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Raw evidence quoted from the vehicle (log lines, OS errors, sensor names) stays as is.
VERBATIM = ("[", "x/y/z", "charging_state=", "hvac_state=", "state=", "RSRP=", "PreArm", "GPS",
            "3D mag", "parachute_armed", "2026-", "/dev/", "/etc/", "vcgencmd")


def engine_strings():
    cfg = {"name": "v", "watch_units": ["mission.service", "perception.service",
                                        "uploader.service", "px4.service"],
           "custom_actions": {"trigger_ffc": {"argv": ["x"],
                                              "description": "Force a thermal-camera flat-field correction"}},
           "action_secret": "s", "heal_step_wait_s": 0}
    out = set()
    for fault in sim.FAULTS:
        for heal in (False, True):
            a = agent.Agent(dict(cfg), simulate=True, faults=[fault])
            for _ in range(8 if heal else 0):
                a.diagnose(heal=True)
            r = a.diagnose()
            now = time.time()
            for age_h in (0.1, 5):
                d = dispatch.decide(r, {f["key"]: now - age_h * 3600 for f in r["findings"]},
                                    a.runner.audit_mem, None, now)
                out |= {d["headline"], d["explain"]}
                out |= {i.get("rule") for i in d["items"]} | {i.get("why") for i in d["items"]}
                out |= set((d.get("work_order") or "").split("\n")[3:])  # skip id/date lines
            for f in r["findings"]:
                out |= {f["title"], f["detail"], f["fix"]}
                rb = f["runbook"]
                out |= set(rb["steps"]) | {rb["verify"]} | set(rb.get("bring", []))
                if rb.get("action"):
                    out.add(rb["action"]["label"])
            for c in r["root_causes"]:
                out |= {c["cause"], c["action"]}
    for rb in runbooks.RUNBOOKS:
        out |= set(rb["steps"]) | {rb["verify"]} | set(rb.get("bring", []))
    for h in rootcause.HYPOTHESES:
        out |= {h["cause"], h["action"]}
    out |= set(fleetcorr.SITE_HINTS.values()) | {v[3] for v in logs.CHECKS.values()}
    return sorted(s for s in out if s and s.strip() and not s.startswith(VERBATIM))


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SpanishCoverageTest(unittest.TestCase):
    def test_every_engine_message_is_translated(self):
        strings = engine_strings()
        script = """
const fs = require('fs');
global.window = {}; global.localStorage = {getItem: () => 'es', setItem() {}};
global.navigator = {language: 'es'}; global.document = {documentElement: {}};
eval(fs.readFileSync(process.argv[2], 'utf8'));
window.I18N.set('es');
const items = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
console.log(JSON.stringify(items.filter(s => window.I18N.tr(s) === s)));
"""
        with tempfile.TemporaryDirectory() as tmp:
            js, data = os.path.join(tmp, "check.js"), os.path.join(tmp, "strings.json")
            open(js, "w").write(script)
            json.dump(strings, open(data, "w"))
            res = subprocess.run(["node", js, os.path.join(ROOT, "fleetdebug", "static", "i18n.js"),
                                  data], capture_output=True, text=True, check=True)
        missing = json.loads(res.stdout)
        self.assertEqual(missing, [], f"{len(missing)} message(s) have no Spanish translation")


if __name__ == "__main__":
    unittest.main()
