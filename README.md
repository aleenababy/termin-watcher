# termin-watcher

Get an alert on your computer (and optionally your phone) when an **earlier appointment** opens up at your Ausländerbehörde / Ausländeramt.

It checks the booking page every few minutes, reads the earliest free slot, and alerts you only when that slot is **before your deadline**. It does **not** book anything for you. You still book the appointment yourself.

It works out of the box with **TEVIS** booking sites (`termine.<city>.de/...`), which many German offices use (Aachen, and many other cities and districts). Other sites can be supported by changing one setting (see [Other booking sites](#other-booking-sites)).

Runs on **macOS, Windows and Linux**. No dependencies beyond Python 3.9+, or use the standalone executable.

---

## 1. Install

**Option A: standalone executable (no Python needed)**
Download the file for your system from the [Releases page](../../releases):
`termin-watcher-macos`, `termin-watcher-windows.exe` or `termin-watcher-linux`.

- macOS / Linux: `chmod +x termin-watcher-macos` and run it as `./termin-watcher-macos ...`.
  On macOS, the first time, right-click the file › Open, because it isn't signed by Apple.
- Windows: run it from PowerShell, for example `.\termin-watcher-windows.exe init`.
  Windows SmartScreen may warn you because the file isn't signed. Choose "More info › Run anyway".

**Option B: with Python (recommended if you have Python)**

```bash
pipx install git+https://github.com/aleenababy/termin-watcher
# or: pip install git+https://github.com/aleenababy/termin-watcher
```

## 2. Find your booking page URL

1. Open your office's online booking site.
2. Pick the service you need (for example "Beratungs- und Antragsservice", "Blaue Karte", "Niederlassungserlaubnis").
3. Click through until the page that shows the **location and "Nächster Termin"** (next appointment).
4. Copy that page's address from the browser's address bar.

Example (Aachen, Beratungs- und Antragsservice):
`https://termine.staedteregion-aachen.de/auslaenderamt/location?mdt=95&select_cnc=1&cnc-341=1&...`

## 3. Set it up

```bash
termin-watcher init
```

It asks for:

| Setting | Example | Meaning |
|---|---|---|
| Name | `Ausländeramt Aachen` | Shown in the alert |
| Booking page URL | `https://termine...location?...` | The page from step 2 |
| Deadline | `2026-12-20` | Alert only for slots **before** this date |
| Interval | `5` | Minutes between checks (minimum 5) |
| ntfy topic | `my-secret-topic-8271` | Optional phone push (see below) |

Or set everything in one line:

```bash
termin-watcher init --non-interactive --name "Ausländeramt Aachen" \
  --url "https://termine.staedteregion-aachen.de/auslaenderamt/location?..." \
  --deadline 2026-12-20 --interval 5
```

## 4. Try it

```bash
termin-watcher check          # one real check, prints the earliest slot
termin-watcher check --test   # forces an alert for the current earliest slot
termin-watcher test-notify    # just tests the alert
```

## 5. Run it in the background

```bash
termin-watcher install      # checks every N minutes, even after a restart
termin-watcher status       # shows the config and the last log lines
termin-watcher uninstall    # stops it
```

- macOS: launchd agent · Windows: Task Scheduler · Linux: systemd user timer (or crontab)
- It **removes itself** once the deadline date is reached.
- Your computer must be on and awake for checks to run.

Prefer not to install a background job? Keep a terminal window open with:

```bash
termin-watcher run
```

## Changing the deadline or the office

Run `termin-watcher init` again, or pass flags to any command:

```bash
termin-watcher install --deadline 2027-01-15
termin-watcher install --url "https://termine.<other-city>.de/..." --name "ABH Köln"
```

The config is a plain JSON file you can also edit directly:

- macOS: `~/Library/Application Support/termin-watcher/config.json`
- Windows: `%APPDATA%\termin-watcher\config.json`
- Linux: `~/.config/termin-watcher/config.json`

You can keep several configs (for example for two offices) with `--config path/to/file.json`. There's an example in [`examples/aachen.json`](examples/aachen.json).

## Alerts

By default you get a desktop notification, a pop-up window, a sound, and the booking page opens in your browser. Turn each one on or off in the `notify` section of the config.

**Phone push (free, no account):** install the **ntfy** app (iOS / Android) and subscribe to a hard-to-guess topic name, for example `abh-aachen-x7k2q9`. Put the same name in `notify.ntfy_topic`. Anyone who knows the topic name can read the messages, so don't use a guessable one.

**Email:** fill in `email_to`, `smtp_host`, `smtp_port`, `smtp_user`. Put the password in the environment variable `TERMIN_SMTP_PASSWORD` rather than in the file. For Gmail, use `smtp.gmail.com`, port `587`, and an [app password](https://support.google.com/accounts/answer/185833).

## Other booking sites

The earliest slot is found with a regular expression (`date_regex` in the config). The default matches TEVIS pages ("Nächster Termin ab 17.02.2027, 09:40 Uhr"). For a different site, change `date_regex` so that group 1 is the date (`DD.MM.YYYY`) and the optional group 2 is the time. If the site needs pages to be visited first to start a session, list them in `warmup_urls`. Pull requests that add presets for other cities are welcome.

## Please use it responsibly

- Keep the interval at 5 minutes or more. Booking servers are public infrastructure, shared by everyone who needs an appointment.
- This is for people looking for **their own** appointment. Don't use it to grab or resell slots.
- Check your office's terms of use. If a site forbids automated access, don't use the tool on it.
- The tool only reads the public availability page. It never logs in, books, or enters personal data.

## License

MIT
