"""Build a single self-contained HTML demo of the fleet console.

    python3 tools/build_demo.py [out.html]

The page needs no server. Every vehicle state the demo can reach, and every
remote-action result, is computed here by the real rules engine, root-cause
correlator and action runner against the simulator, then embedded as JSON;
tools/demo_shim.js answers the dashboard's /api/* calls from that data.
BLUEPRINT.md is rendered into a Blueprint tab (needs `pip install markdown`;
it falls back to preformatted text without it).
"""

import csv
import io
import json
import os
import random
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fleetdebug import agent as agent_mod  # noqa: E402
from fleetdebug import dispatch, fleetcorr, logs, runbooks, sim  # noqa: E402
from fleetdebug.demo import FAULT_AGE_H, vehicles  # noqa: E402
from fleetdebug.history import History  # noqa: E402

NOW = time.time()
rnd = random.Random(7)


AUTO_FIXABLE = {"vpn_down", "dns_fail", "modem_hung", "sim_no_service", "clock_skew",
                "config_drift", "service_disabled", "geofence_missing", "disk_full",
                "crashed_node", "oom", "upload_backlog"}


def key_of(a):
    return (",".join(sorted(a.faults)) or "healthy") + "@" + getattr(a, "sim_version", "2.4.1")


def candidate_actions(a):
    for unit in a.config.get("watch_units", []):
        yield "restart_service", {"unit": unit}
    for name in ("reboot", "restart_modem", "restart_network", "restart_vpn", "switch_sim",
                 "resync_time", "reupload_geofence", "rollback_software"):
        yield name, {}
    yield "vacuum_journal", {"max_size": "200M"}
    yield "restore_config", {"path": "/etc/drone/mission.yaml"}
    for name in a.config.get("custom_actions") or {}:
        yield name, {}


def new_agent(v, heal):
    cfg = {**v["cfg"], "heal_step_wait_s": 0}
    if not heal:
        cfg["auto_remediate"] = []
    a = agent_mod.Agent(cfg, simulate=True, faults=v["faults"])
    a.sim_version = v["version"]
    if v["mode"] == "flap":
        a.sim_flap = set(v["faults"])
    return a


def first_seen_for(v, result):
    """When each current problem started, from the demo's FAULT_AGE_H."""
    probe = new_agent(v, heal=False)
    started = {}
    for fault in v["faults"]:
        probe.faults = {fault}
        for f in probe.diagnose()["findings"]:
            started.setdefault(f["key"], NOW - FAULT_AGE_H.get(fault, 0.2) * 3600)
    return {f["key"]: started.get(f["key"], NOW - 0.4 * 3600) for f in result["findings"]}


def with_dispatch(v, result, audit):
    result["dispatch"] = dispatch.decide(result, first_seen_for(v, result), audit, None, NOW)
    return result


def explore(v, index):
    """Initial state (after any self-healing), then every state reachable by remote actions."""
    a = new_agent(v, heal=True)
    seq = []
    if v["mode"] in ("preheal", "flap"):
        for _ in range(14):
            a.diagnose(heal=True)
    step_recs = []  # the self-heal record that leads into each live state
    if v["mode"] == "live":
        a.diagnose(heal=True)  # the page opens after the first self-healing step
        step_recs.append(None)
        for _ in range(8):
            seq.append(a.diagnose())
            n = len(a.runner.audit_mem)
            a.diagnose(heal=True)
            if len(a.runner.audit_mem) == n:
                break
            step_recs.append(dict(a.runner.audit_mem[-1], via="self-heal",
                                  vehicle=v["cfg"]["name"]))
        else:
            seq.append(a.diagnose())
        if len(step_recs) > len(seq):
            seq.append(a.diagnose())
    auto = [dict(r, via="self-heal") for r in a.runner.audit_mem[:1 if seq else None]]
    if v["mode"] == "preheal":  # these happened over the past hours
        for k, r in enumerate(auto):
            r["ts"] = NOW - (len(auto) - k) * rnd.uniform(1500, 6000)
    for r in auto:
        r["vehicle"] = v["cfg"]["name"]

    states, transitions = {}, {}
    if seq:
        for k, res in enumerate(seq):
            states[f"seq{k}"] = {"result": with_dispatch(v, res, auto), "fkey": None,
                                 "catalog": a.runner.catalog(),
                                 "auto_new": step_recs[k] if k < len(step_recs) else None}
        start = "seq0"
    else:
        states["init"] = {"result": with_dispatch(v, a.diagnose(), auto), "fkey": key_of(a),
                          "catalog": a.runner.catalog()}
        start = "init"

    # Operator actions: explore from every fault state seen above, with no self-healing,
    # so each click shows exactly what that one action does.
    b = new_agent(v, heal=False)
    roots = []
    if seq:
        for k, res in enumerate(seq):
            snap = res["snapshot"]
            roots.append((f"seq{k}", set(snap["active_faults"]),
                          snap["software"]["version"]))
    else:
        roots.append(("init", set(a.faults), a.sim_version))
    queue = []
    for name, faults, ver in roots:
        b.faults, b.sim_version = set(faults), ver
        states[name]["fkey"] = key_of(b)
        queue.append((set(faults), ver))
    seen = set()
    while queue:
        faults, ver = queue.pop(0)
        b.faults, b.sim_version = set(faults), ver
        k = key_of(b)
        if k in seen:
            continue
        seen.add(k)
        if k not in states:
            states[k] = {"result": with_dispatch(v, b.diagnose(), []), "fkey": k,
                         "catalog": b.runner.catalog()}
        for action, params in candidate_actions(b):
            b.faults, b.sim_version = set(faults), ver
            rec = b.runner.execute(action, params, "demo")
            nxt = key_of(b)
            pkey = json.dumps(params, sort_keys=True, separators=(",", ":"))
            transitions[f"{k}|{action}|{pkey}"] = {"record": rec, "next": nxt}
            transitions.setdefault(f"{k}|{action}|*", transitions[f"{k}|{action}|{pkey}"])
            queue.append((set(b.faults), b.sim_version))
    push = v["push"]
    meta = {"name": v["cfg"]["name"], "site": v["cfg"]["site"], "mode": "push" if push else "pull",
            "kind": "full", "age_s": round(rnd.uniform(0.5, 4.0), 1),
            "url": None if push else f"http://10.8.0.{11 + index}:8765",
            "auto_seq": [f"seq{k}" for k in range(len(seq))]}
    return {"name": v["cfg"]["name"], "start": start, "states": states,
            "transitions": transitions, "meta": meta, "audit": auto}


def silent_vehicle():
    """A push vehicle that stopped reporting 7 minutes ago (what Fleet.view() shows)."""
    a = agent_mod.Agent({"name": "rover-03", "site": "Pipeline Corridor", "auto_remediate": [],
                         "action_secret": "x", "skip_preconditions": ["docked"],
                         "watch_units": ["mission.service"]}, simulate=True)
    r = a.diagnose()
    age = 412
    r["status"] = "unreachable"
    r["preflight"] = {"decision": "NO-GO", "blockers": ["Vehicle silent"], "holds": [],
                      "advisories": []}
    silent = [{"severity": "critical", "component": "link", "title": f"No heartbeat for {age}s",
               "detail": "Last known state is shown below. The vehicle keeps logging locally "
                         "and will backfill on reconnect.",
               "fix": "Check carrier coverage/outage at the site, modem health on the last "
                      "report, and base station power."}]
    runbooks.attach(silent, {})
    r["findings"] = silent + r["findings"]
    r["root_causes"] = []
    r["dispatch"] = dispatch.decide(r, {silent[0]["key"]: NOW - age}, [], None, NOW)
    return {"name": "rover-03", "start": "silent",
            "states": {"silent": {"result": r, "catalog": a.runner.catalog(), "fkey": "silent"}},
            "transitions": {},
            "meta": {"name": "rover-03", "site": "Pipeline Corridor", "mode": "push",
                     "kind": "full", "age_s": age, "silent": True, "url": None, "auto_seq": []}}


def synth_history(specs):
    """Seven days of simulated checks, every 3 h, with faults that come and go."""
    h = History(":memory:")
    steps = list(range(7 * 8))
    windy = {s: rnd.random() < 0.12 for s in steps}  # site-wide weather holds
    for v in specs:
        cfg = {**v["cfg"], "auto_remediate": []}
        a = agent_mod.Agent(cfg, simulate=True)
        a.sim_version = v["version"]
        hardware = [f for f in v["faults"] if f not in AUTO_FIXABLE | {"gps_loss", "low_battery"}]
        onset = {f: rnd.randint(30, 52) for f in hardware}
        for s in steps:
            ts = NOW - (len(steps) - s) * 3 * 3600
            f = {x for x in hardware if s >= onset[x]}
            if cfg["site"] == "Solar Farm A" and rnd.random() < 0.15:
                f.add("gps_loss")
            if windy[s] and cfg["site"] in ("Mine Pit 3", "Substation 12"):
                f.add("high_wind")
            a.faults = f
            h.record(cfg["name"], a.diagnose(), ts)
    out = {"recurring": h.recurring(None, 168, 25), "availability": h.availability(168),
           "by_component": h.by_component(168)}
    # How a week of problems got resolved on a fleet this size (illustrative numbers):
    # connectivity and people errors are frequent and fix themselves; hardware is rare.
    out["resolution"] = {"auto": 96 + rnd.randint(0, 12), "remote": 7, "technician": 3}
    out["policy"] = dispatch.DEFAULT_POLICY
    out["simulated"] = True
    return out


def render_blueprint(name="BLUEPRINT.md"):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        text = f.read()
    try:
        import markdown
        html = markdown.markdown(text, extensions=["tables", "fenced_code"])
    except ImportError:
        import html as _h
        html = f"<pre>{_h.escape(text)}</pre>"
    html = html.replace("<table>", '<div class="scroll"><table>').replace("</table>",
                                                                          "</table></div>")
    return html


def main(out, standalone=False):
    specs = vehicles(8)
    built = [explore(v, i) for i, v in enumerate(specs)] + [silent_vehicle()]
    audit = sorted([r for b in built for r in b.pop("audit", [])], key=lambda r: -r["ts"])
    rows = sim.flight_log_rows(faults=("vibration", "gps_loss", "battery_sag"))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    data = {"vehicles": built, "audit": audit, "history": synth_history(specs),
            "site_hints": fleetcorr.SITE_HINTS,
            "log_checks": {k: list(v) for k, v in logs.CHECKS.items()},
            "built_at": NOW}

    with open(os.path.join(ROOT, "fleetdebug", "static", "index.html")) as f:
        page = f.read()
    with open(os.path.join(ROOT, "tools", "demo_shim.js")) as f:
        shim = f.read()
    with open(os.path.join(ROOT, "fleetdebug", "static", "i18n.js")) as f:
        i18n = f.read()

    head = page[page.index("<title>"):page.index("</head>")]
    body = page[page.index("<body>") + len("<body>"):page.index("</body>")]

    def js_json(obj):
        return json.dumps(obj, default=str, separators=(",", ":")).replace("</", "<\\/")

    body = body.replace('<script src="i18n.js"></script>', f"<script>\n{i18n}\n</script>", 1)
    body = body.replace('<button data-tab="audit" data-i18n>Action log</button>',
                        '<button data-tab="audit" data-i18n>Action log</button>\n'
                        '    <button data-tab="blueprint" data-i18n>Blueprint</button>')
    about_en = ' <a href="index.html">About this project</a>' if standalone else ''
    about_es = ' <a href="index.html">Sobre este proyecto</a>' if standalone else ''
    banner = ('<div class="demo-note" role="note"><span class="l-en"><b>Interactive demo with a '
              'simulated fleet.</b> Vehicles fix connectivity and settings problems by themselves; '
              'drone-05 and rover-02 are doing it right now (watch for about 30 s). Each vehicle '
              'says in plain words whether to wait, fix it remotely, or send a technician. All '
              'results come from the real rules engine and action runner.' + about_en + '</span>'
              '<span class="l-es"><b>Demostración interactiva con una flota simulada.</b> Los '
              'vehículos reparan solos los problemas de conectividad y configuración; drone-05 y '
              'rover-02 lo están haciendo ahora mismo (observe unos 30 s). Cada vehículo indica '
              'en palabras simples si hay que esperar, solucionarlo a distancia o enviar un '
              'técnico. Todos los resultados provienen del motor de reglas y del ejecutor de '
              'acciones reales.' + about_es + '</span></div>')
    body = body.replace("<main>", "<main>\n  " + banner, 1)
    blueprint_es = render_blueprint("BLUEPRINT.es.md")
    body = body.replace("</main>", '  <section id="tab-blueprint" class="hidden">\n'
                        '    <article class="card prose"><div class="l-en">' + render_blueprint() +
                        '</div><div class="l-es">' + (blueprint_es or render_blueprint()) +
                        "</div></article>\n  </section>\n</main>", 1)
    extra_css = """<style>
html[lang="es"] .l-en, html:not([lang="es"]) .l-es { display: none; }
.demo-note { background: var(--info-bg); color: var(--ink); border-radius: 10px; padding: 10px 14px;
             margin-bottom: 12px; font-size: 13px; }
.prose { max-width: 920px; margin: 0 auto; padding: 20px clamp(16px, 4vw, 40px); line-height: 1.6; }
.prose h1 { font-size: 26px; line-height: 1.25; margin: 4px 0 12px; text-wrap: balance; }
.prose h2 { font-size: 19px; margin: 8px 0 8px; text-transform: none; letter-spacing: 0; color: var(--ink); text-wrap: balance; }
.prose h3 { font-size: 15px; margin: 22px 0 6px; text-transform: none; letter-spacing: 0;
            color: var(--ink); }
.prose h4 { font-size: 14px; margin: 18px 0 6px; }
.prose p, .prose li { max-width: 72ch; }
.prose pre { max-height: none; font-size: 12px; line-height: 1.4; white-space: pre; }
.prose code { font-size: 12.5px; background: var(--bg); padding: 1px 4px; border-radius: 4px; }
.prose pre code { background: none; padding: 0; }
.prose blockquote { margin: 12px 0; padding: 10px 16px; border-left: 3px solid var(--accent);
                    background: var(--info-bg); border-radius: 0 8px 8px 0; }
.prose table { margin: 8px 0 16px; }
.prose hr { border: 0; border-top: 1px solid var(--line); margin: 24px 0; }
.prose { border-top: 4px solid var(--signal); }
.prose h1 { color: var(--accent); }
.prose h2 { background: linear-gradient(90deg, var(--h3-band), transparent 85%); border-left: 5px solid var(--signal);
            padding: 7px 12px; border-radius: 0 8px 8px 0; margin-top: 26px; }
.prose h3 { color: var(--accent); }
.prose code { background: var(--warn-bg); }
.prose pre { background: var(--stripe); border-left: 4px solid var(--accent); }
</style>"""
    scripts = (f"<script>window.DEMO_STATIC = true;\nwindow.DEMO = {js_json(data)};\n"
               f"window.DEMO_SAMPLE_CSV = {js_json(buf.getvalue())};</script>\n"
               f"<script>\n{shim}\n</script>\n")
    body = body.replace("<script>", scripts + "<script>", 1)
    if standalone:  # a normal web page for any static host
        out_html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                    '<meta name="description" content="Interactive demo: a remote debugging and '
                    'self-healing console for autonomous drones and rovers.">\n'
                    + head.strip() + "\n" + extra_css + "\n</head>\n<body>\n" + body.strip() +
                    "\n</body>\n</html>\n")
    else:  # published as an Artifact, which adds the document skeleton itself
        out_html = ('<meta name="claude:viewport-fit-sides" content="cover">\n' + head.strip() +
                    "\n" + extra_css + "\n" + body.strip() + "\n")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write(out_html)
    n_states = sum(len(b["states"]) for b in built)
    print(f"wrote {out} ({len(out_html) // 1024} KB, {len(built)} vehicles, "
          f"{n_states} states, {sum(len(b['transitions']) for b in built)} action results)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--standalone"]
    main(args[0] if args else os.path.join(ROOT, "dist", "drone-fleet-debugger.html"),
         standalone="--standalone" in sys.argv)
