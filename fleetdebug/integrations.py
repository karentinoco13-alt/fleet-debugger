"""Outbound integrations: alert webhooks and export to an external ops platform.

The export is a generic, documented JSON event. Point `endpoint` at whatever
your operations platform or middleware accepts (a fleet-management or analytics
platform, a ticketing system, Slack, Teams, PagerDuty, or an MQTT/HTTP bridge).
"""

import json
import time
import urllib.request

SEV_RANK = {"ok": 0, "info": 0, "warning": 1, "critical": 2, "unreachable": 2}


def event_payload(result):
    """Stable schema for downstream systems (versioned so consumers can evolve)."""
    return {
        "schema": "fleetdebug.event/v1",
        "ts": time.time(),
        "drone": result.get("name"),
        "site": result.get("site"),
        "status": result.get("status"),
        "preflight": (result.get("preflight") or {}).get("decision"),
        "dispatch": (result.get("dispatch") or {}).get("decision"),
        "root_causes": [r["cause"] for r in result.get("root_causes", [])],
        "findings": [{k: f[k] for k in ("severity", "component", "title", "detail", "fix")}
                     for f in result.get("findings", [])],
    }


def _post(url, body, headers=None, timeout=5):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


class Notifier:
    """Sends an alert when a drone's status gets worse (not on every poll)."""

    def __init__(self, targets):
        # targets: [{"type": "webhook"|"slack", "url": ..., "min_severity": "warning",
        #            "headers": {...}}]
        self.targets = targets or []
        self.last = {}

    def handle(self, result):
        name, status = result.get("name"), result.get("status", "ok")
        prev = self.last.get(name, "ok")
        self.last[name] = status
        if SEV_RANK.get(status, 0) <= SEV_RANK.get(prev, 0):
            return []
        sent = []
        for t in self.targets:
            if SEV_RANK.get(status, 0) < SEV_RANK.get(t.get("min_severity", "warning"), 1):
                continue
            try:
                if t["type"] == "slack":
                    top = result.get("findings", [])[:5]
                    text = (f"*{name}* is *{status.upper()}* "
                            f"(pre-flight: {(result.get('preflight') or {}).get('decision')})\n"
                            + "\n".join(f"• {f['title']}" for f in top))
                    _post(t["url"], {"text": text})
                else:
                    _post(t["url"], event_payload(result), t.get("headers"))
                sent.append(t["url"])
            except Exception as exc:
                print(f"notify {t.get('url')} failed: {exc}")
        return sent
