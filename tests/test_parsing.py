from datetime import date

from termin_watcher import checker, cli
from termin_watcher.config import Config, DEFAULT_DATE_REGEX

TEVIS_HTML = """
<dl class="grid suggest_location_tbl"><dt>Name</dt><dd>Ausländeramt - Trierer Straße 1</dd>
<dt>Nächster Termin</dt><dd>ab 17.02.2027, 09:40 Uhr</dd></dl>
<dl><dt>Name</dt><dd>Außenstelle</dd><dt>N&auml;chster Termin</dt><dd>ab 03.12.2026, 11:00 Uhr</dd></dl>
<footer>Stand 01.01.2020</footer>
"""


def test_finds_earliest_slot_and_ignores_other_dates():
    slots = checker.find_slots(TEVIS_HTML, DEFAULT_DATE_REGEX)
    assert [str(s) for s in slots] == ["03.12.2026, 11:00", "17.02.2027, 09:40"]


def test_no_slot():
    assert checker.find_slots("<p>Derzeit keine Termine</p>", DEFAULT_DATE_REGEX) == []


def test_open_url_for_tevis():
    cfg = Config(url="https://termine.example.de/auslaenderamt/location?mdt=1&cnc-1=1")
    assert checker.default_open_url(cfg) == "https://termine.example.de/auslaenderamt/"


def _cfg(tmp_path, monkeypatch, deadline, slot_day):
    monkeypatch.setattr(cli, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "log_path", lambda: tmp_path / "log")
    monkeypatch.setattr(cli, "state_path", lambda: tmp_path / "state")
    sent = []
    monkeypatch.setattr(cli.notify, "alert", lambda cfg, t, b, u: sent.append(b))
    monkeypatch.setattr(cli.checker, "check",
                        lambda cfg: checker.Result(True, checker.Slot(slot_day, "09:00"), "x"))
    return Config(url="https://x.de/a/location?x=1", deadline=deadline), sent


def test_alert_only_before_deadline_and_once(tmp_path, monkeypatch):
    cfg, sent = _cfg(tmp_path, monkeypatch, "2999-01-01", date(2998, 6, 1))
    cli.run_check(cfg); cli.run_check(cfg)
    assert len(sent) == 1  # same slot is not re-announced


def test_no_alert_after_deadline(tmp_path, monkeypatch):
    cfg, sent = _cfg(tmp_path, monkeypatch, "2999-01-01", date(2999, 2, 1))
    cli.run_check(cfg)
    assert sent == []


def test_test_mode_always_alerts(tmp_path, monkeypatch):
    cfg, sent = _cfg(tmp_path, monkeypatch, "2999-01-01", date(2998, 6, 1))
    cli.run_check(cfg, test=True); cli.run_check(cfg, test=True)
    assert len(sent) == 2


def test_config_roundtrip(tmp_path):
    c = Config(name="X", url="https://a.de", deadline="2027-01-01")
    c.notify.ntfy_topic = "abc"
    p = tmp_path / "c.json"; c.save(p)
    assert Config.load(p).notify.ntfy_topic == "abc"
