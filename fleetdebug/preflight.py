"""Pre-mission go/no-go gate.

Run this before an autonomous launch (e.g. as a mission-scheduler hook). It's
deliberately conservative: any critical finding in a flight-relevant
component blocks the launch. Weather and payload issues block it too, but
they can be overridden by the operator.
"""

BLOCKING = {"flight-controller", "gps", "estimator", "airframe", "power", "safety",
            "dock", "link", "software", "thermal"}
OVERRIDABLE = {"weather", "payload"}


def evaluate(findings):
    blockers, holds, advisories = [], [], []
    for f in findings:
        if f["component"] in OVERRIDABLE and f["severity"] in ("critical", "warning"):
            holds.append(f)
        elif f["severity"] == "critical" and f["component"] in BLOCKING:
            blockers.append(f)
        elif f["severity"] in ("critical", "warning"):
            advisories.append(f)
    if blockers:
        decision = "NO-GO"
    elif holds:
        decision = "HOLD"
    else:
        decision = "GO"
    return {
        "decision": decision,
        "blockers": [f["title"] for f in blockers],
        "holds": [f["title"] for f in holds],
        "advisories": [f["title"] for f in advisories],
    }
