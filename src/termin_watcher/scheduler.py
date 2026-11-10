"""Install / remove a background job that runs `check` every N minutes.

macOS: launchd agent · Linux: systemd user timer (falls back to crontab) · Windows: Task Scheduler
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "io.github.termin-watcher"
TASK_NAME = "TerminWatcher"


def self_command(config_path: Path) -> list[str]:
    """Command that runs one check, for both pip installs and frozen executables."""
    if getattr(sys, "frozen", False):  # PyInstaller binary
        base = [sys.executable]
    else:
        exe = sys.executable
        if sys.platform == "win32":  # pythonw avoids a console window popping up
            w = Path(exe).with_name("pythonw.exe")
            exe = str(w) if w.exists() else exe
        base = [exe, "-m", "termin_watcher"]
    return base + ["check", "--config", str(config_path)]


# ---------------- macOS ----------------
def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _install_mac(cmd: list[str], minutes: int, log: Path) -> str:
    args = "".join(f"<string>{_xml(c)}</string>" for c in cmd)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>StartInterval</key><integer>{minutes * 60}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{_xml(str(log))}</string>
  <key>StandardErrorPath</key><string>{_xml(str(log))}</string>
</dict></plist>
"""
    p = _plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
    p.write_text(plist, encoding="utf-8")
    subprocess.run(["launchctl", "load", str(p)], check=True)
    return f"launchd agent {p}"


def _uninstall_mac() -> None:
    p = _plist_path()
    subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
    p.unlink(missing_ok=True)


def _xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------- Linux ----------------
def _systemd_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _quote(c: str) -> str:
    return '"' + c.replace('"', '\\"') + '"' if any(ch in c for ch in ' "\'') else c


def _install_linux(cmd: list[str], minutes: int, log: Path) -> str:
    if shutil.which("systemctl") and subprocess.run(
            ["systemctl", "--user", "show-environment"], capture_output=True).returncode == 0:
        d = _systemd_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "termin-watcher.service").write_text(
            "[Unit]\nDescription=Appointment slot check\n\n[Service]\nType=oneshot\n"
            f"ExecStart={' '.join(_quote(c) for c in cmd)}\n", encoding="utf-8")
        (d / "termin-watcher.timer").write_text(
            "[Unit]\nDescription=Run appointment slot check\n\n[Timer]\nOnBootSec=1min\n"
            f"OnUnitActiveSec={minutes}min\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n",
            encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "termin-watcher.timer"], check=True)
        return "systemd user timer termin-watcher.timer"
    if not shutil.which("crontab"):
        raise SystemExit("Neither systemd (user) nor crontab found. Use `termin-watcher run` instead.")
    line = f"*/{minutes} * * * * {' '.join(_quote(c) for c in cmd)} >> {_quote(str(log))} 2>&1 # termin-watcher"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    keep = [l for l in cur.splitlines() if "# termin-watcher" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(keep + [line]) + "\n", text=True, check=True)
    return "crontab entry"


def _uninstall_linux() -> None:
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "disable", "--now", "termin-watcher.timer"], capture_output=True)
        for f in ("termin-watcher.service", "termin-watcher.timer"):
            (_systemd_dir() / f).unlink(missing_ok=True)
    if shutil.which("crontab"):
        cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        keep = [l for l in cur.splitlines() if "# termin-watcher" not in l]
        if keep != cur.splitlines():
            subprocess.run(["crontab", "-"], input="\n".join(keep) + "\n", text=True)


# ---------------- Windows ----------------
def _install_windows(cmd: list[str], minutes: int, log: Path) -> str:
    tr = subprocess.list2cmdline(cmd)
    subprocess.run(["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(minutes),
                    "/TN", TASK_NAME, "/TR", tr], check=True)
    subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], capture_output=True)
    return f"Task Scheduler task '{TASK_NAME}'"


def _uninstall_windows() -> None:
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], capture_output=True)


# ---------------- public ----------------
def install(config_path: Path, minutes: int, log: Path) -> str:
    cmd = self_command(config_path)
    if sys.platform == "darwin":
        return _install_mac(cmd, minutes, log)
    if sys.platform == "win32":
        return _install_windows(cmd, minutes, log)
    return _install_linux(cmd, minutes, log)


def uninstall() -> None:
    if sys.platform == "darwin":
        _uninstall_mac()
    elif sys.platform == "win32":
        _uninstall_windows()
    else:
        _uninstall_linux()
