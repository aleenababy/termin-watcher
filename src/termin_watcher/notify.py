"""Cross-platform alerts: desktop notification, pop-up, sound, browser, ntfy, email."""
from __future__ import annotations

import os
import shutil
import smtplib
import subprocess
import sys
import urllib.request
import webbrowser
from email.message import EmailMessage

from .config import Config


def _run(cmd: list[str], background: bool = False) -> None:
    try:
        if background:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except Exception:
        pass


def _esc_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _esc_ps(s: str) -> str:
    return s.replace("'", "''")


def desktop(title: str, body: str) -> None:
    if sys.platform == "darwin":
        t, b = _esc_applescript(title), _esc_applescript(body)
        _run(["osascript", "-e", f'display notification "{b}" with title "{t}" sound name "Glass"'])
        _run(["osascript", "-e", f'display alert "{t}" message "{b}"'], background=True)
    elif sys.platform == "win32":
        t, b = _esc_ps(title), _esc_ps(body)
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
            f"$n.ShowBalloonTip(15000,'{t}','{b}','Info');"
            f"[System.Windows.Forms.MessageBox]::Show('{b}','{t}');$n.Dispose()"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             creationflags=flags)
        except Exception:
            pass
    else:
        if shutil.which("notify-send"):
            _run(["notify-send", "-u", "critical", title, body])
        if shutil.which("zenity"):
            _run(["zenity", "--info", f"--title={title}", f"--text={body}"], background=True)
        elif shutil.which("kdialog"):
            _run(["kdialog", "--title", title, "--msgbox", body], background=True)


def sound() -> None:
    if sys.platform == "darwin":
        for _ in range(2):
            _run(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif sys.platform == "win32":
        try:
            import winsound
            for _ in range(3):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
    else:
        for player, f in (("paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"),
                          ("canberra-gtk-play", None)):
            if shutil.which(player):
                _run([player, f] if f else [player, "-i", "complete"])
                return
        print("\a", end="", flush=True)


def ntfy(server: str, topic: str, title: str, body: str, click: str) -> None:
    req = urllib.request.Request(
        f"{server.rstrip('/')}/{topic}", data=body.encode("utf-8"), method="POST",
        headers={"Title": title.encode("ascii", "replace").decode(), "Priority": "high",
                 "Tags": "calendar", "Click": click},
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print(f"ntfy failed: {e}")


def email(cfg: Config, title: str, body: str) -> None:
    n = cfg.notify
    password = os.environ.get("TERMIN_SMTP_PASSWORD") or n.smtp_password
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = title, n.smtp_user or n.email_to, n.email_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(n.smtp_host, n.smtp_port, timeout=30) as s:
            s.starttls()
            if n.smtp_user:
                s.login(n.smtp_user, password)
            s.send_message(msg)
    except Exception as e:
        print(f"email failed: {e}")


def alert(cfg: Config, title: str, body: str, open_url: str) -> None:
    n = cfg.notify
    if n.desktop:
        desktop(title, body)
    if n.ntfy_topic:
        ntfy(n.ntfy_server, n.ntfy_topic, title, body, open_url)
    if n.email_to and n.smtp_host:
        email(cfg, title, f"{body}\n\nBook here: {open_url}")
    if n.open_browser:
        try:
            webbrowser.open(open_url)
        except Exception:
            pass
    if n.sound:
        sound()
