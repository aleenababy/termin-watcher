"""Fetch the booking page and find the earliest free slot."""
from __future__ import annotations

import html as htmllib
import http.cookiejar
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

from .config import Config

USER_AGENT = (
    "Mozilla/5.0 (compatible; termin-watcher; +https://github.com/aleenababy/termin-watcher) "
    "personal appointment availability check"
)
TIMEOUT = 30


@dataclass
class Slot:
    day: date
    time: str = ""

    def __str__(self) -> str:
        s = self.day.strftime("%d.%m.%Y")
        return f"{s}, {self.time}" if self.time else s


class Session:
    def __init__(self) -> None:
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.opener.addheaders = [("User-Agent", USER_AGENT), ("Accept-Language", "de-DE,de;q=0.9,en;q=0.5")]

    def get(self, url: str) -> str:
        with self.opener.open(url, timeout=TIMEOUT) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(charset, errors="replace")


def tevis_warmup(url: str, session: Session) -> list[str]:
    """TEVIS sites (termine.<city>.de/<office>/location?...) need a session that
    was started on the office start page and its 'select2?md=N' page."""
    p = urlparse(url)
    if "/location" not in p.path:
        return []
    base = urljoin(url, "./")
    visited = [base]
    start = session.get(base)
    m = re.search(r"select2\?md=(\d+)", start)
    if m:
        step2 = urljoin(base, f"select2?md={m.group(1)}")
        session.get(step2)
        visited.append(step2)
    return visited


def default_open_url(cfg: Config) -> str:
    if cfg.open_url:
        return cfg.open_url
    if "/location" in urlparse(cfg.url).path:
        return urljoin(cfg.url, "./")
    return cfg.url


def page_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", htmllib.unescape(text))


def find_slots(html: str, date_regex: str) -> list[Slot]:
    slots = []
    for m in re.finditer(date_regex, page_text(html), flags=re.IGNORECASE):
        try:
            d = datetime.strptime(m.group(1), "%d.%m.%Y").date()
        except ValueError:
            continue
        t = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
        slots.append(Slot(d, t))
    return sorted(slots, key=lambda s: (s.day, s.time))


@dataclass
class Result:
    ok: bool
    earliest: Slot | None
    message: str


def check(cfg: Config) -> Result:
    s = Session()
    try:
        if cfg.warmup_urls:
            for u in cfg.warmup_urls:
                s.get(u)
        else:
            tevis_warmup(cfg.url, s)
        html = s.get(cfg.url)
    except Exception as e:  # network errors etc.
        return Result(False, None, f"could not load page: {e}")

    slots = find_slots(html, cfg.date_regex)
    if not slots:
        if re.search(r"Fehlermeldung|Kein g(?:ü|ue)ltiger", page_text(html), re.I):
            return Result(False, None, "page returned an error (session or URL problem)")
        return Result(True, None, "no free slot shown")
    return Result(True, slots[0], f"earliest slot: {slots[0]}")
