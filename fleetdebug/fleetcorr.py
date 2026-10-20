"""Fleet-wide correlation: is it the vehicle, the site, or the software?

A single vehicle with a GPS fault is probably a cable or antenna. Every
vehicle at one site losing GPS in the same window is jamming, an obstruction,
or space weather. Every vehicle on v2.5.0 crashing the mission node is a
software regression. Telling these apart early saves truck rolls and stops
bad rollouts.
"""

from collections import defaultdict

# Group findings into broad signatures so "Low satellite count (5)" and
# "Low satellite count (6)" count as the same problem.
SIGNATURES = [
    ("gnss", ("gps", "satellite", "hdop", "pos_horiz")),
    ("cellular", ("cellular", "unreachable", "no heartbeat for", "cannot reach")),
    ("weather", ("wind", "precipitation")),
    ("power", ("mains power", "under-voltage")),
    ("compass", ("compass", "mag")),
    ("software-crash", ("not running", "python error", "traceback", "failed")),
    ("memory", ("memory", "oom")),
    ("upload", ("not reaching the cloud",)),
    ("thermal", ("°c", "climate")),
]

SITE_HINTS = {
    "gnss": "Several vehicles at one site: suspect RF jamming/interference, a new "
            "obstruction, or ionospheric activity, not individual antennas.",
    "cellular": "Several vehicles at one site: suspect a carrier outage or a tower issue. "
                "Check the carrier status page; fail over to the secondary SIM.",
    "weather": "Site-wide weather hold; expected, not a fault.",
    "power": "Site power problem; check the site feed and UPS.",
    "compass": "Several vehicles: suspect new site infrastructure (steel, power lines) "
               "near the base stations.",
    "thermal": "Site-wide heat: check the ambient conditions and HVAC sizing for the season.",
    "upload": "Site uplink saturated or a cloud-side ingest problem.",
}


def signature(f):
    text = (f["title"] + " " + f.get("detail", "")).lower()
    for sig, words in SIGNATURES:
        if any(w in text for w in words):
            return sig
    return None


def correlate(results, min_vehicles=2, min_share=0.5):
    """results: latest diagnosis per vehicle. Returns site- and version-level incidents."""
    out = []
    for key, label in (("site", "site"), ("version", "software version")):
        groups = defaultdict(list)
        for r in results:
            v = r.get("site") if key == "site" else \
                ((r.get("snapshot") or {}).get("software") or {}).get("version")
            if v:
                groups[v].append(r)
        for gname, members in groups.items():
            hits = defaultdict(set)
            for r in members:
                for f in r.get("findings", []):
                    if f["severity"] in ("critical", "warning"):
                        sig = signature(f)
                        if sig:
                            hits[sig].add(r["name"])
            for sig, vehicles in hits.items():
                if key == "version" and sig in ("weather", "cellular", "power", "gnss"):
                    continue  # environment, not software
                if key == "site" and sig in ("software-crash", "memory"):
                    continue
                share = len(vehicles) / len(members)
                if len(vehicles) >= min_vehicles and share >= min_share:
                    hint = SITE_HINTS.get(sig, "") if key == "site" else (
                        f"Common to vehicles on {gname}: suspect a software regression. "
                        "Pause the rollout and compare against the previous version.")
                    out.append({"scope": label, "group": gname, "signature": sig,
                                "vehicles": sorted(vehicles), "share": round(share, 2),
                                "hint": hint})
    out.sort(key=lambda x: (-len(x["vehicles"]), x["scope"]))
    return out
