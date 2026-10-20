"""P0 heartbeat: one tiny line for the worst links (satellite SBD, SMS, LoRa).

Iridium SBD carries 340 bytes and SMS 160 characters, so this encodes the
minimum an operator needs to decide whether to worry:

    HB1|dock07|c|N|v2.4.1|b13.1|s3|f12|t1792464902|crit=fc,gps|a3f1

  status: o/w/c, preflight: G/H/N, battery V, sats, findings count, unix time,
  up to 4 short component codes of critical findings, 16-bit checksum.
"""

import zlib

ST = {"ok": "o", "warning": "w", "critical": "c"}
PF = {"GO": "G", "HOLD": "H", "NO-GO": "N"}
COMP = {"flight-controller": "fc", "gps": "gps", "estimator": "ekf", "airframe": "air",
        "power": "pwr", "safety": "saf", "dock": "dock", "link": "lnk", "software": "sw",
        "compute": "cpu", "thermal": "tmp", "payload": "pay", "weather": "wx",
        "storage": "dsk", "data-pipeline": "up"}
COMP_REV = {v: k for k, v in COMP.items()}


def encode(result, ts):
    s = result.get("snapshot") or {}
    t = s.get("telemetry") or {}
    crit = []
    for f in result.get("findings", []):
        c = COMP.get(f["component"], "x")
        if f["severity"] == "critical" and c not in crit:
            crit.append(c)
    parts = ["HB1", str(result.get("name", "?")).replace("|", "_")[:16], ST.get(result.get("status"), "c"),
             PF.get((result.get("preflight") or {}).get("decision"), "N"),
             "v" + str((s.get("software") or {}).get("version", "?"))[:10],
             "b" + (f"{t['battery_voltage']:.1f}" if t.get("battery_voltage") else "-"),
             "s" + str(t.get("gps_satellites", "-")),
             "f" + str(len(result.get("findings", []))), "t" + str(int(ts)),
             "crit=" + ",".join(crit[:4])]
    body = "|".join(parts)
    return f"{body}|{zlib.crc32(body.encode()) & 0xffff:04x}"


def decode(line):
    line = line.strip()
    body, _, crc = line.rpartition("|")
    if f"{zlib.crc32(body.encode()) & 0xffff:04x}" != crc:
        raise ValueError("checksum mismatch")
    p = body.split("|")
    if p[0] != "HB1" or len(p) != 10:
        raise ValueError("not an HB1 heartbeat")
    st = {v: k for k, v in ST.items()}[p[2]]
    pf = {v: k for k, v in PF.items()}[p[3]]
    crit = [c for c in p[9].split("=", 1)[1].split(",") if c]
    return {
        "name": p[1], "status": st, "kind": "heartbeat", "ts": float(p[8][1:]),
        "preflight": {"decision": pf, "blockers": [], "holds": [], "advisories": []},
        "software_version": p[4][1:],
        "battery_voltage": None if p[5] == "b-" else float(p[5][1:]),
        "gps_satellites": None if p[6] == "s-" else p[6][1:],
        "findings": [{"severity": "critical", "component": COMP_REV.get(c, c),
                      "title": f"{COMP_REV.get(c, c)} critical (heartbeat only)",
                      "detail": "Reported over the low-bandwidth backup link; details "
                                "will arrive when the main link returns.",
                      "fix": "Wait for the full report, or pull a bundle once connected."}
                     for c in crit],
        "root_causes": [],
    }
