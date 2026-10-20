"""Debug bundles: one archive with everything needed to investigate an incident.

Field engineers shouldn't have to SSH into a drone sitting in a remote dock
over a flaky LTE link and type commands. Create a bundle once, then analyze it
offline or attach it to a ticket.
"""

import io
import json
import os
import shutil
import subprocess
import tarfile
import time

COMMANDS = {
    "journal_boot.txt": ["journalctl", "-b", "--no-pager", "-n", "5000"],
    "journal_errors.txt": ["journalctl", "-p", "warning", "-b", "--no-pager"],
    "dmesg.txt": ["dmesg", "-T"],
    "ps.txt": ["ps", "auxww", "--sort=-%cpu"],
    "systemctl_failed.txt": ["systemctl", "--failed", "--no-pager"],
    "ip_addr.txt": ["ip", "addr"],
    "ip_route.txt": ["ip", "route"],
    "usb.txt": ["lsusb", "-t"],
    "video_devices.txt": ["v4l2-ctl", "--list-devices"],
    "pip_freeze.txt": ["python3", "-m", "pip", "freeze"],
    "df.txt": ["df", "-h"],
    "mmcli.txt": ["mmcli", "-m", "0"],  # LTE modem (ModemManager)
}


def _add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = time.time()
    tar.addfile(info, io.BytesIO(data))


def create(result, out_dir=".", extra_paths=(), run_commands=True):
    name = result.get("name") or "drone"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, f"debug-{name}-{stamp}.tar.gz")
    root = f"debug-{name}-{stamp}"
    with tarfile.open(path, "w:gz") as tar:
        _add_bytes(tar, f"{root}/diagnosis.json",
                   json.dumps(result, indent=2, default=str).encode())
        _add_bytes(tar, f"{root}/SUMMARY.md", summary_markdown(result).encode())
        if run_commands and not result.get("snapshot", {}).get("simulated"):
            for fname, cmd in COMMANDS.items():
                if not shutil.which(cmd[0]):
                    continue
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=20)
                    _add_bytes(tar, f"{root}/system/{fname}", r.stdout + r.stderr)
                except Exception as exc:
                    _add_bytes(tar, f"{root}/system/{fname}", str(exc).encode())
        for p in extra_paths:  # flight logs, rosbags, app logs from the config
            if os.path.exists(p):
                tar.add(p, arcname=f"{root}/files/{os.path.basename(p)}")
    return path


def summary_markdown(result):
    lines = [f"# Debug report: {result.get('name')}",
             "", f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
             f"- Status: **{result.get('status', '?').upper()}**"]
    pf = result.get("preflight")
    if pf:
        lines.append(f"- Pre-flight: **{pf['decision']}**")
    rc = result.get("root_causes") or []
    if rc:
        lines += ["", "## Likely root causes"]
        for r in rc:
            lines.append(f"- **{r['cause']}** (evidence: {', '.join(r['evidence'])})  \n"
                         f"  → {r['action']}")
    lines += ["", "## Findings"]
    for f in result.get("findings", []):
        lines.append(f"- [{f['severity'].upper()}] {f['component']}: {f['title']}")
        if f.get("detail"):
            lines.append(f"  - {f['detail']}")
        lines.append(f"  - fix: {f['fix']}")
    if not result.get("findings"):
        lines.append("- none")
    return "\n".join(lines) + "\n"
