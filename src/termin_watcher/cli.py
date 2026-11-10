"""termin-watcher: get alerted when an earlier appointment slot opens up."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

from . import __version__, checker, notify, scheduler
from .config import Config, config_dir, default_config_path


def log_path() -> Path:
    return config_dir() / "check.log"


def state_path() -> Path:
    return config_dir() / "last_alert.txt"


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line)
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config(args) -> tuple[Config, Path]:
    path = Path(args.config) if args.config else default_config_path()
    cfg = Config.load(path) if path.exists() else Config()
    if getattr(args, "url", None):
        cfg.url = args.url
    if getattr(args, "deadline", None):
        cfg.deadline = args.deadline
    if getattr(args, "name", None):
        cfg.name = args.name
    if getattr(args, "interval", None):
        cfg.interval_minutes = args.interval
    if not cfg.url or not cfg.deadline:
        raise SystemExit(f"No URL/deadline configured. Run `termin-watcher init` first (config: {path}).")
    cfg.validate()
    return cfg, path


# ---------------- commands ----------------
def cmd_init(args) -> None:
    path = Path(args.config) if args.config else default_config_path()
    cfg = Config.load(path) if path.exists() else Config()

    def ask(label: str, current: str) -> str:
        v = input(f"{label}{f' [{current}]' if current else ''}: ").strip()
        return v or current

    cfg.name = args.name or ask("Name of the office (for the alert text)", cfg.name)
    print("\nOpen your office's booking site, choose your service, and go to the step that\n"
          "shows the location / next free appointment. Copy that page's address.")
    cfg.url = args.url or ask("Booking page URL", cfg.url)
    cfg.deadline = args.deadline or ask("Alert for slots before (YYYY-MM-DD)", cfg.deadline)
    cfg.interval_minutes = args.interval or int(ask("Check every N minutes", str(cfg.interval_minutes)))
    if not args.non_interactive:
        cfg.notify.ntfy_topic = ask("Optional ntfy topic for phone push (empty = off)", cfg.notify.ntfy_topic)
    cfg.validate()
    cfg.save(path)
    print(f"\nSaved {path}\nNext: `termin-watcher check` to try it, then `termin-watcher install`.")


def run_check(cfg: Config, test: bool = False) -> int:
    today = date.today()
    deadline = cfg.deadline_date()
    if not test and today >= deadline:
        log(f"deadline {deadline} reached - removing background job")
        scheduler.uninstall()
        return 0

    res = checker.check(cfg)
    log(res.message)
    if not res.ok:
        return 2
    slot = res.earliest
    if slot and slot.day < deadline and slot.day >= today:
        last = state_path().read_text(encoding="utf-8").strip() if state_path().exists() else ""
        if test or last != str(slot):
            if not test:
                state_path().write_text(str(slot), encoding="utf-8")
            title = f"{cfg.name}: slot available" + (" (TEST)" if test else "")
            notify.alert(cfg, title, f"Earliest slot: {slot}. Book it now!", checker.default_open_url(cfg))
            log(f"ALERT sent for {slot}")
    return 0


def cmd_check(args) -> None:
    cfg, _ = load_config(args)
    if args.test:  # pretend the deadline is far away so the current slot triggers an alert
        cfg.deadline = "2999-12-31"
    sys.exit(run_check(cfg, test=args.test))


def cmd_run(args) -> None:
    cfg, _ = load_config(args)
    print(f"Checking every {cfg.interval_minutes} min until {cfg.deadline}. Ctrl+C to stop.")
    while date.today() < cfg.deadline_date():
        run_check(cfg)
        time.sleep(cfg.interval_minutes * 60)


def cmd_install(args) -> None:
    cfg, path = load_config(args)
    cfg.save(path)  # persist any flag overrides so the background job uses them
    where = scheduler.install(path, cfg.interval_minutes, log_path())
    print(f"Installed ({where}). Checking every {cfg.interval_minutes} min until {cfg.deadline}.")
    print(f"Log: {log_path()}")


def cmd_uninstall(args) -> None:
    scheduler.uninstall()
    print("Background job removed.")


def cmd_test_notify(args) -> None:
    cfg = Config.load(Path(args.config)) if args.config else (
        Config.load(default_config_path()) if default_config_path().exists() else Config())
    notify.alert(cfg, f"{cfg.name}: test alert", "If you see this, alerts work.",
                 checker.default_open_url(cfg) if cfg.url else "https://example.org")
    print("Test alert sent.")


def cmd_status(args) -> None:
    path = Path(args.config) if args.config else default_config_path()
    print(f"Config: {path}")
    print(Config.load(path).to_json() if path.exists() else "(none yet)")
    if log_path().exists():
        print("\nLast log lines:")
        print("".join(log_path().read_text(encoding="utf-8").splitlines(True)[-10:]))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="termin-watcher", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, overrides=True):
        sp.add_argument("--config", help="path to config.json (default: per-user config folder)")
        if overrides:
            sp.add_argument("--url", help="booking page URL")
            sp.add_argument("--deadline", help="alert for slots before this date, YYYY-MM-DD")
            sp.add_argument("--name", help="office name shown in alerts")
            sp.add_argument("--interval", type=int, help="minutes between checks (min 5)")
        return sp

    s = common(sub.add_parser("init", help="create or edit the config"))
    s.add_argument("--non-interactive", action="store_true", help="use flags only, no prompts")
    s.set_defaults(func=cmd_init)
    s = common(sub.add_parser("check", help="check once now"))
    s.add_argument("--test", action="store_true", help="force an alert for the current earliest slot")
    s.set_defaults(func=cmd_check)
    common(sub.add_parser("run", help="keep checking in this window (no install)")).set_defaults(func=cmd_run)
    common(sub.add_parser("install", help="run checks in the background")).set_defaults(func=cmd_install)
    common(sub.add_parser("uninstall", help="stop background checks"), False).set_defaults(func=cmd_uninstall)
    common(sub.add_parser("test-notify", help="send a test alert"), False).set_defaults(func=cmd_test_notify)
    common(sub.add_parser("status", help="show config and recent log"), False).set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    if args.cmd == "init" and args.non_interactive:
        import builtins
        builtins.input = lambda *_: ""  # type: ignore
    args.func(args)
