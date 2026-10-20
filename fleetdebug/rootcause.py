"""Root-cause correlation.

Individual rules report symptoms. Field failures usually show up as several
symptoms with one cause (a brownout drops USB, which drops the FC link,
which aborts the mission). These hypotheses look for those patterns and
rank them by how much of the evidence they explain.
"""


def _has(findings, component=None, words=()):
    for f in findings:
        if component and f["component"] != component:
            continue
        text = (f["title"] + " " + f["detail"]).lower()
        if all(w.lower() in text for w in words):
            return f
    return None


HYPOTHESES = [
    {
        "cause": "Power brownout on the companion computer / FC rail",
        "evidence": [("power", ("under-voltage",)), ("link", ("usb disconnect",)),
                     ("flight-controller", ("heartbeat",))],
        "min": 2,
        "action": "Measure the 5V/12V rails under load; check the BEC rating and connectors. "
                  "Brownouts during takeoff current spikes are typical.",
    },
    {
        "cause": "Loose or vibrating flight-controller cable",
        "evidence": [("link", ("usb disconnect",)), ("flight-controller", ("heartbeat",)),
                     ("airframe", ("vibration",))],
        "min": 2,
        "action": "Secure the FC USB/UART connector (hot glue / locking JST), add strain relief, "
                  "and fix the vibration source.",
    },
    {
        "cause": "GNSS degradation (obstruction or RF interference)",
        "evidence": [("gps", ("fix",)), ("gps", ("satellite",)), ("gps", ("hdop",)),
                     ("estimator", ("pos_horiz",)), ("flight-controller", ("gps",))],
        "min": 2,
        "action": "Check the antenna's sky view at the base station, and keep it away from the LTE "
                  "modem and camera USB3 lines (USB3 emits noise in the GPS L1 band). "
                  "Try a shielded cable or a ground plane.",
    },
    {
        "cause": "Magnetic interference on the compass",
        "evidence": [("estimator", ("compass",)), ("flight-controller", ("compass",)),
                     ("flight-controller", ("mag",))],
        "min": 1,
        "action": "Look for nearby steel structures or high-current cables near the mag; "
                  "recalibrate away from the base station; consider an external mast-mounted compass.",
    },
    {
        "cause": "Propulsion problem (damaged prop / motor bearing)",
        "evidence": [("airframe", ("vibration",)), ("estimator", ("velocity",))],
        "min": 1,
        "action": "Inspect and replace the props; spin each motor by hand to feel for bearing "
                  "roughness; check the FC damping mount.",
    },
    {
        "cause": "Thermal problem degrading compute",
        "evidence": [("thermal", ("°c",)), ("compute", ("cpu",)), ("dock", ("climate",)),
                     ("payload", ("dropping frames",))],
        "min": 2,
        "action": "Fix the cooling first (base station HVAC, companion fan); the CPU and frame symptoms "
                  "should clear once temperatures drop.",
    },
    {
        "cause": "Software fault in the onboard Python stack",
        "evidence": [("software", ("not running",)), ("software", ("python error",)),
                     ("compute", ("memory",)), ("compute", ("oom",)),
                     ("software", ("failed",))],
        "min": 2,
        "action": "Pull the debug bundle and read the traceback. If memory is high too, look "
                  "for a leak (tracemalloc, unbounded queues/caches in ROS callbacks). Add "
                  "Restart=on-failure and MemoryMax= to the systemd unit.",
    },
    {
        "cause": "Base station not recharging the vehicle",
        "evidence": [("dock", ("not charging",)), ("power", ("battery low",)),
                     ("dock", ("landing marker",))],
        "min": 1,
        "action": "Clean the contacts and check the landing accuracy. A drone that lands "
                  "off-center won't charge, and the next mission aborts on low battery.",
    },
    {
        "cause": "Connectivity: cellular backhaul degraded",
        "evidence": [("link", ("cellular",)), ("data-pipeline", ("cloud",)),
                     ("link", ("cannot reach",))],
        "min": 1,
        "action": "Check the carrier status and antenna; if it persists, move the base station antenna "
                  "or add a second SIM/carrier. Data will upload once the link recovers.",
    },
]


def correlate(findings):
    results = []
    for h in HYPOTHESES:
        matched = []
        for comp, words in h["evidence"]:
            f = _has(findings, comp, words)
            if f and f not in matched:
                matched.append(f)
        if len(matched) >= h["min"]:
            results.append({
                "cause": h["cause"],
                "confidence": round(len(matched) / len(h["evidence"]), 2),
                "evidence": [m["title"] for m in matched],
                "action": h["action"],
            })
    results.sort(key=lambda r: (-len(r["evidence"]), -r["confidence"]))
    return results
