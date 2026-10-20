"""Dispatch policy: when have we run out of remote options and need someone on site?

Each problem on a vehicle follows its runbook route (see runbooks.py), and the
policy turns route + how long it has lasted + what was already tried into a
decision with an explicit rule a non-engineer can read:

  auto    The vehicle is working through its own fix ladder (self-healing);
          nobody needs to do anything unless it runs out.
  remote  Try the remote fix. After `max_remote_attempts` attempts that
          didn't clear it, send someone.
  wait    Expected to clear by itself. If it lasts longer than its
          `wait_limit_h`, send someone. (Weather has no limit: a technician
          can't fix the wind.)
  site    Needs hands on site: critical -> send someone now;
          warning -> schedule a visit within `site_warning_within_h`.

Vehicle decision, in priority order:
  dispatch-now > try-remote > dispatch-scheduled > wait > ok
"""

import time

DEFAULT_POLICY = {
    "max_remote_attempts": 2,
    "wait_limit_h": {"gps": 2, "estimator": 2, "thermal": 2, "power": 4, "payload": 1,
                     "link": 1, "flight-controller": 2, "weather": None, "default": 4},
    "site_warning_within_h": 72,
}

ORDER = {"dispatch-now": 0, "auto-fixing": 1, "try-remote": 2, "dispatch-scheduled": 3,
         "wait": 4, "escalated": 5, "ok": 6}


def _fmt_h(h):
    if h is None:
        return "-"
    if h < 1:
        return f"{max(1, round(h * 60))} min"
    return f"{h:.1f} h" if h < 10 else f"{round(h)} h"


def _attempts(finding, audit, since):
    act = (finding.get("runbook") or {}).get("action")
    if not act:
        return []
    return [r for r in audit
            if r.get("action") == act["name"] and (r.get("params") or {}) == act["params"]
            and r.get("status") in ("done", "failed", "blocked") and r.get("ts", 0) >= since - 1]


def decide(result, first_seen, audit, policy=None, now=None):
    """result: a diagnosis; first_seen: {finding key: ts}; audit: action records for this vehicle."""
    p = {**DEFAULT_POLICY, **(policy or {})}
    limits = {**DEFAULT_POLICY["wait_limit_h"], **(p.get("wait_limit_h") or {})}
    now = now or time.time()
    healing = result.get("healing") or {}
    items = []
    for f in result.get("findings", []):
        if f["severity"] == "info":
            continue
        rb = f.get("runbook") or {"route": "site", "steps": [f.get("fix", "")], "bring": []}
        key = f.get("key") or f["title"]
        age_h = (now - first_seen.get(key, now)) / 3600
        it = {"title": f["title"], "component": f["component"], "severity": f["severity"],
              "route": rb["route"], "age_h": round(age_h, 2), "action": rb.get("action"),
              "bring": rb.get("bring", []), "verify": rb.get("verify", "")}
        heal = healing.get(key)
        if heal:
            it["auto"] = heal
        if heal and not heal["exhausted"]:
            it["decision"] = "auto-fixing"
            it["rule"] = "The vehicle fixes this itself, one step at a time; you're told if it runs out."
            done = ", ".join(t.replace("_", " ") for t in heal["tried"]) or "starting"
            it["why"] = f"Fixing itself: step {heal['step'] + 1} of {heal['of']} (done so far: {done})."
        elif heal and heal["exhausted"]:
            # Covered by the "Automatic fixes used up" item, which carries the next step.
            it["decision"] = "escalated"
            it["rule"] = "Automatic fixes are used up; see that item for the next step."
            it["why"] = f"Tried automatically: {', '.join(t.replace('_', ' ') for t in heal['tried'])}."
        elif rb["route"] == "remote":
            tries = _attempts(f, audit, first_seen.get(key, now))
            n, mx = len(tries), p["max_remote_attempts"]
            it["attempts"] = n
            it["tried"] = [{"ts": t["ts"], "status": t.get("status"), "operator": t.get("operator"),
                            "error": t.get("error")} for t in tries]
            it["rule"] = f"Try the remote fix up to {mx} times; if it doesn't hold, send someone."
            if n >= mx:
                it["decision"] = "dispatch-now" if f["severity"] == "critical" else "dispatch-scheduled"
                it["why"] = (f"Remote fix tried {n} time(s) and the problem is still there.")
            else:
                it["decision"] = "try-remote"
                it["why"] = (f"Remote fix not tried yet." if n == 0 else
                             f"Tried {n} of {mx} times; try again or wait for the next check.")
        elif rb["route"] == "wait":
            comp = "weather" if f["component"] == "weather" else f["component"]
            limit = limits.get(comp, limits["default"])
            it["limit_h"] = limit
            if limit is None:
                it["decision"] = "wait"
                it["rule"] = "Hold missions until it passes. A technician can't fix this."
                it["why"] = f"Present for {_fmt_h(age_h)}."
            elif age_h > limit:
                it["decision"] = "dispatch-now" if f["severity"] == "critical" else "dispatch-scheduled"
                it["rule"] = f"Should clear by itself; send someone if it lasts over {_fmt_h(limit)}."
                it["why"] = f"Present for {_fmt_h(age_h)}, over the {_fmt_h(limit)} limit."
            else:
                it["decision"] = "wait"
                it["rule"] = f"Should clear by itself; send someone if it lasts over {_fmt_h(limit)}."
                it["why"] = (f"Present for {_fmt_h(age_h)}. Send someone if it's still here in "
                             f"{_fmt_h(limit - age_h)}.")
                it["deadline_h"] = round(limit - age_h, 2)
        else:
            if f["severity"] == "critical":
                it["decision"] = "dispatch-now"
                it["rule"] = "Physical problem; it can't be fixed remotely. Send someone now."
                it["why"] = "No remote fix exists for this."
            else:
                within = p["site_warning_within_h"]
                it["decision"] = "dispatch-scheduled"
                it["rule"] = (f"Physical problem, not urgent. Fix it on a visit within "
                              f"{_fmt_h(within)}.")
                it["why"] = "No remote fix exists for this."
        items.append(it)

    items.sort(key=lambda i: ORDER[i["decision"]])
    decision = items[0]["decision"] if items else "ok"
    if decision == "escalated":
        decision = "ok"
    counts = {k: sum(i["decision"] == k for i in items) for k in ORDER}
    headline, explain = {
        "dispatch-now": ("Send a technician now",
                         "Every remote option has been used or none exists for these problems."),
        "auto-fixing": ("Fixing itself: no action needed",
                        "The vehicle is working through its automatic fixes. You'll be told "
                        "only if it runs out of options."),
        "try-remote": ("Not yet: try the remote fixes first",
                       "Some problems can still be fixed from here. Run them, then check again."),
        "dispatch-scheduled": ("Schedule a technician visit",
                               "Remote options are used up, but nothing is urgent."),
        "wait": ("Wait: these should clear by themselves",
                 "Missions are on hold. The app tells you if they last past their limit."),
        "ok": ("No action needed", "All checks pass."),
    }[decision]
    if decision == "dispatch-now" and counts["try-remote"]:
        explain += (f" While the technician is on the way, {counts['try-remote']} remote fix(es) "
                    "can still be tried.")
    out = {"decision": decision, "headline": headline, "explain": explain, "counts": counts,
           "items": items}
    if decision.startswith("dispatch"):
        out["work_order"] = work_order(result, items, now)
    return out


def work_order(result, items, now):
    snap = result.get("snapshot") or {}
    send = [i for i in items if i["decision"].startswith("dispatch")]
    lines = [f"WORK ORDER: {result.get('name')} at {result.get('site') or 'unknown site'}",
             f"Created {time.strftime('%Y-%m-%d %H:%M', time.localtime(now))}"
             + (f" · software {snap['software'].get('version')}" if snap.get("software") else ""),
             "Priority: " + ("URGENT, today" if any(i["decision"] == "dispatch-now" for i in send)
                             else "Scheduled visit"),
             "", "PROBLEMS TO FIX ON SITE"]
    for n, i in enumerate(send, 1):
        lines.append(f"{n}. {i['title']}  ({i['why']})")
    tried = [(i, t) for i in items for t in i.get("tried", [])]
    lines += ["", "ALREADY TRIED REMOTELY"]
    if tried:
        for i, t in tried:
            when = time.strftime("%m-%d %H:%M", time.localtime(t["ts"]))
            act = (i.get("action") or {}).get("label", "remote fix")
            lines.append(f"- {when} {act} by {t.get('operator')}: {t.get('status')}"
                         + (f" ({t['error']})" if t.get("error") else ", problem came back"))
    else:
        lines.append("- Nothing: no remote fix exists for these problems.")
    bring = sorted({b for i in send for b in i.get("bring", [])})
    lines += ["", "BRING"] + [f"- {b}" for b in (bring or ["Standard toolkit and laptop"])]
    lines += ["", "SAFETY", "- The vehicle is NO-GO. Confirm it is disarmed before opening the base station.",
              "- Keep clear of the propellers; remove them before any work on the motors.",
              "", "DONE WHEN"]
    lines += [f"- {i['verify']}" for i in send if i.get("verify")]
    lines.append("- The vehicle shows GO in the dashboard after a re-check.")
    return "\n".join(lines)
