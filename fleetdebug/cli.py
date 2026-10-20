"""Command line entry point: `python -m fleetdebug <command>`."""

import argparse
import os
import csv
import json
import sys
import threading

from . import agent as agent_mod
from . import bundle, console, logs, sim

COLORS = {"critical": "\033[31m", "warning": "\033[33m", "info": "\033[36m",
          "ok": "\033[32m"}
RESET = "\033[0m"


def load_config(path):
    if not path:
        return {}
    with open(path) as f:
        return json.load(f)


def _c(sev, text):
    return f"{COLORS.get(sev, '')}{text}{RESET}" if sys.stdout.isatty() else text


def print_report(result):
    pf = result.get("preflight", {})
    print(f"\n{result.get('name')}: {_c(result['status'], result['status'].upper())}"
          f"   pre-flight: {pf.get('decision')}")
    for rc in result.get("root_causes", []):
        print(f"  ROOT CAUSE? {rc['cause']}  (evidence: {', '.join(rc['evidence'])})")
        print(f"         → {rc['action']}")
    if not result["findings"]:
        print("  No problems found.")
    for f in result["findings"]:
        print(f"  [{_c(f['severity'], f['severity'][:4].upper())}] "
              f"{f['component']}: {f['title']}")
        if f["detail"]:
            print(f"         {f['detail']}")
        print(f"         fix: {f['fix']}")


def cmd_diagnose(args):
    result = _agent(args).diagnose()
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)
    return {"ok": 0, "warning": 1, "critical": 2}[result["status"]]


def _agent(args):
    a = agent_mod.Agent(load_config(args.config), simulate=args.simulate,
                        faults=args.fault or [])
    if a.mav:  # give the MAVLink reader a moment to receive messages
        import time
        time.sleep(args.wait)
    return a


def cmd_preflight(args):
    result = _agent(args).diagnose()
    pf = result["preflight"]
    if args.json:
        print(json.dumps(pf, indent=2))
    else:
        color = {"GO": "ok", "HOLD": "warning"}.get(pf["decision"], "critical")
        print(_c(color, pf["decision"]))
        for k in ("blockers", "holds", "advisories"):
            for item in pf[k]:
                print(f"  {k[:-1]}: {item}")
    return {"GO": 0, "HOLD": 1}.get(pf["decision"], 2)


def cmd_bundle(args):
    result = _agent(args).diagnose()
    cfg = load_config(args.config)
    path = bundle.create(result, args.out, cfg.get("bundle_paths", []))
    print(f"wrote {path}")


def cmd_agent(args):
    cfg = load_config(args.config)
    a = agent_mod.Agent(cfg, simulate=args.simulate, faults=args.fault or [])
    up = cfg.get("uplink", {})
    url = args.uplink or up.get("url")
    if url:
        from .uplink import Uplink
        link = Uplink(a, url, up.get("token"), up.get("interval_s", 30),
                      up.get("spool_path", "/var/lib/fleetdebug/spool.jsonl"),
                      fallback_cmd=up.get("fallback_cmd"),
                      fallback_interval_s=up.get("fallback_interval_s", 300))
        threading.Thread(target=link.run, daemon=True).start()
        print(f"pushing diagnoses to {url} (store-and-forward)")
    if a.healer.playbooks:
        threading.Thread(target=a.heal_loop, args=(cfg.get("heal_interval_s", 30),),
                         daemon=True).start()
        print(f"self-healing enabled ({len(a.healer.playbooks)} playbook(s))")
    if args.no_server:
        threading.Event().wait()
    agent_mod.serve(a, args.host, args.port)


def cmd_console(args):
    console.serve(load_config(args.config), args.host, args.port)


def cmd_demo(args):
    """Start the simulated demo fleet and the console, all in one process."""
    import tempfile
    from .demo import vehicles
    from .uplink import Uplink
    spool_dir = tempfile.mkdtemp(prefix="fleetdebug-spool-")
    drones, port = [], args.base_port
    for v in vehicles(args.drones):
        cfg = {**v["cfg"], "heal_step_wait_s": 8}
        a = agent_mod.Agent(cfg, simulate=True, faults=v["faults"])
        a.sim_version = v["version"]
        if v["mode"] == "flap":
            a.sim_flap = set(v["faults"])
        threading.Thread(target=a.heal_loop, args=(4,), daemon=True).start()
        entry = {"name": cfg["name"], "site": cfg["site"], "action_secret": cfg["action_secret"]}
        if v["push"]:
            # Push vehicles start before the console is up, so their first reports
            # spool locally and backfill once it's listening: store-and-forward.
            link = Uplink(a, f"http://127.0.0.1:{args.port}", interval_s=5,
                          spool_path=os.path.join(spool_dir, f"{cfg['name']}.jsonl"))
            threading.Thread(target=link.run, daemon=True).start()
        else:
            server = agent_mod.make_server(a, "127.0.0.1", port)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            entry["url"] = f"http://127.0.0.1:{port}"
            port += 1
        drones.append(entry)
    console.serve({"drones": drones, "history_db": args.history_db, "poll_interval_s": 5,
                   "silent_after_s": 30}, args.host, args.port)


def cmd_hash_password(args):
    import getpass
    print(console.hash_password(getpass.getpass("password: ")))


def cmd_analyze(args):
    rows = logs.load(args.log)
    report = logs.analyze(rows)
    if args.json:
        print(json.dumps(report, indent=2))
        return 2 if any(e["severity"] == "critical" for e in report["events"]) else 0
    print(f"\n{args.log}: {report['summary']}\n")
    for e in report["events"]:
        print(f"  t={e['start_s']:>7.1f}s  +{e['duration_s']:>5.1f}s  "
              f"[{_c(e['severity'], e['severity'][:4].upper())}] {e['title']} "
              f"({e['field']} worst={e['worst']}, limit={e['threshold']})")
    crit_tl = [m for m in report.get("timeline", []) if m["critical"]]
    for m in crit_tl:
        print(f"\n  ⚠ t={m['time_s']:.1f}s {m['text']}")
        if m.get("preceded_by"):
            print(f"    preceded by: {', '.join(m['preceded_by'])}")
    print("\n  field                 min      max     mean")
    for k, s in report["stats"].items():
        print(f"  {k:<18} {s['min']:>8} {s['max']:>8} {s['mean']:>8}")
    return 2 if any(e["severity"] == "critical" for e in report["events"]) else 0


def cmd_gen_log(args):
    rows = sim.flight_log_rows(args.duration, faults=args.fault or ["vibration", "gps_loss"])
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="fleetdebug",
                                description="Debug and self-healing toolkit for autonomous Linux/Python vehicles")
    sub = p.add_subparsers(dest="cmd", required=True)

    fault_help = "inject a simulated fault: " + ", ".join(sim.FAULTS)

    d = sub.add_parser("diagnose", help="run all checks once on this machine")
    d.add_argument("-c", "--config")
    d.add_argument("--simulate", action="store_true")
    d.add_argument("--fault", action="append", choices=list(sim.FAULTS), help=fault_help)
    d.add_argument("--json", action="store_true")
    d.add_argument("--wait", type=float, default=3.0, help="seconds to listen to MAVLink")
    d.set_defaults(fn=cmd_diagnose)

    for cmd, fn, h in (("preflight", cmd_preflight, "go/no-go check (exit 0=GO 1=HOLD 2=NO-GO)"),
                       ("bundle", cmd_bundle, "write a debug bundle .tar.gz")):
        x = sub.add_parser(cmd, help=h)
        x.add_argument("-c", "--config")
        x.add_argument("--simulate", action="store_true")
        x.add_argument("--fault", action="append", choices=list(sim.FAULTS), help=fault_help)
        x.add_argument("--wait", type=float, default=3.0)
        if cmd == "preflight":
            x.add_argument("--json", action="store_true")
        else:
            x.add_argument("-o", "--out", default=".")
        x.set_defaults(fn=fn)

    a = sub.add_parser("agent", help="run the on-drone HTTP agent")
    a.add_argument("-c", "--config")
    a.add_argument("--host", default="0.0.0.0")
    a.add_argument("--port", type=int, default=8765)
    a.add_argument("--simulate", action="store_true")
    a.add_argument("--fault", action="append", choices=list(sim.FAULTS), help=fault_help)
    a.add_argument("--uplink", help="console URL to push diagnoses to (store-and-forward)")
    a.add_argument("--no-server", action="store_true",
                   help="push-only: don't open a listening port on the vehicle")
    a.set_defaults(fn=cmd_agent)

    c = sub.add_parser("console", help="run the fleet dashboard")
    c.add_argument("-c", "--config", required=True)
    c.add_argument("--host", default="0.0.0.0")
    c.add_argument("--port", type=int, default=8080)
    c.set_defaults(fn=cmd_console)

    m = sub.add_parser("demo", help="simulated fleet + dashboard, no hardware needed")
    m.add_argument("--base-port", type=int, default=8765)
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--port", type=int, default=8080)
    m.add_argument("--drones", dest="drones", type=int, default=8)
    m.add_argument("--history-db", default=":memory:")
    m.set_defaults(fn=cmd_demo)

    l = sub.add_parser("analyze-log", help="analyze a flight log (.csv, .ulg, .bin)")
    l.add_argument("log")
    l.add_argument("--json", action="store_true")
    l.set_defaults(fn=cmd_analyze)

    hp = sub.add_parser("hash-password", help="hash a console user's password for the config")
    hp.set_defaults(fn=cmd_hash_password)

    g = sub.add_parser("gen-log", help="generate a sample flight log CSV with faults")
    g.add_argument("out")
    g.add_argument("--duration", type=int, default=300)
    g.add_argument("--fault", action="append", choices=["vibration", "gps_loss", "battery_sag"])

    g.set_defaults(fn=cmd_gen_log)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
