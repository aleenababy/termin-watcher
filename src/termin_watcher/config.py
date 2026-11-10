"""Configuration: a JSON file, overridable by command-line flags."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

APP = "termin-watcher"
MIN_INTERVAL = 5  # minutes; be polite to public booking servers

# Matches TEVIS-style pages ("Nächster Termin ab 17.02.2027, 09:40 Uhr"),
# used by many German Ausländerbehörden / Bürgerämter.
DEFAULT_DATE_REGEX = (
    r"N(?:ä|ae|a)chster\s+(?:freier\s+)?Termin\D{0,40}?"
    r"(\d{1,2}\.\d{1,2}\.\d{4})(?:,?\s*(\d{1,2}:\d{2}))?"
)


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Notify:
    desktop: bool = True        # system notification + pop-up window
    sound: bool = True
    open_browser: bool = True   # open the booking start page
    ntfy_topic: str = ""        # phone push via https://ntfy.sh (free app)
    ntfy_server: str = "https://ntfy.sh"
    email_to: str = ""          # leave empty to disable email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    # Password is read from the TERMIN_SMTP_PASSWORD environment variable,
    # or from this field (less safe: stored in plain text).
    smtp_password: str = ""


@dataclass
class Config:
    name: str = "Ausländerbehörde"
    url: str = ""                     # page that shows the next free slot
    deadline: str = ""                # alert only for slots BEFORE this date (YYYY-MM-DD)
    interval_minutes: int = 5
    open_url: str = ""                # page to open on alert (default: derived from url)
    warmup_urls: list[str] = field(default_factory=list)  # visited first to start a session
    date_regex: str = DEFAULT_DATE_REGEX
    notify: Notify = field(default_factory=Notify)

    # ---- helpers ----
    def deadline_date(self) -> date:
        return date.fromisoformat(self.deadline)

    def validate(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise SystemExit("Config error: 'url' must be the full booking page address (https://...).")
        try:
            self.deadline_date()
        except ValueError:
            raise SystemExit("Config error: 'deadline' must look like 2026-12-20.")
        if self.interval_minutes < MIN_INTERVAL:
            print(f"Interval raised to {MIN_INTERVAL} minutes to avoid overloading the booking site.")
            self.interval_minutes = MIN_INTERVAL

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "Config":
        data = json.loads(path.read_text(encoding="utf-8"))
        notify = Notify(**data.pop("notify", {}))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(notify=notify, **known)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
