# Greece Appointment News Monitor

Watches the official Greece-visa news pages for **Pakistan** and alerts you the
moment a **new announcement** appears (e.g. monthly appointment slot releases):

- **Email** — once per new item.
- **Desktop popup** — re-appears **every minute until you click “✓ Got it”**, then
  stops for that item.

It watches **news pages only** (GVC World + Greek Embassy Islamabad). It does
**not** touch the booking scheduler and does **not** book anything — that would
break their rules and risk your clients' applications.

Sources watched:
- GVC World (Pakistan–Greece): <https://pk-gr.gvcworld.eu/en/news>
- Greek Embassy Islamabad: <https://www.mfa.gr/missionsabroad/en/pakistan-en/news/>

---

## Setup (Windows)

From this `news_monitor` folder:

```powershell
# 1. Install the two small dependencies (use the same Python as the scanner)
pip install -r requirements.txt

# 2. Make your config from the example
copy config.example.json config.json
# then open config.json and fill in your email settings (see below)
```

### Email settings (Gmail)
Gmail needs an **App Password** (not your normal password):
1. Turn on 2-Step Verification: <https://myaccount.google.com/security>
2. Create an App Password: <https://myaccount.google.com/apppasswords> → pick
   “Mail” → copy the 16-character code.
3. In `config.json` set:
   - `"username"` and `"from"` → your Gmail address
   - `"app_password"` → that 16-character code
   - `"to"` → where alerts should go (can be the same address)

Other providers: set `smtp_host` / `smtp_port` (465 = SSL, 587 = TLS).

---

## Run

```powershell
# Test that parsing works (fetch once, print what it finds, then exit):
python monitor.py --test

# Test that email works:
python monitor.py --test-email

# Start monitoring (runs 24/7 — leave it open):
python monitor.py
```

- The **first run** records everything currently on the pages as a baseline
  (no alerts) — you only get alerted on posts that appear **after** that.
- Activity is logged to `monitor.log`.

### Run quietly in the background / at startup
- No console window: use `pythonw monitor.py` instead of `python monitor.py`.
- Auto-start with Windows: press `Win+R`, type `shell:startup`, and put a
  shortcut to `pythonw.exe <full path>\monitor.py` in that folder.

---

## Settings you can change (`config.json`)
- `check_interval_seconds` — how often to check (default **120** = 2 min).
  Don't go below ~60s; too fast risks the site blocking you.
- `renotify_seconds` — how often the desktop popup re-appears (default **60**).
- `keywords_only` — `true` = only alert when a title matches a keyword;
  `false` (default) = alert on every new post so nothing is missed.
- `desktop_popup` / `sound` — turn the popup or beep off.

> Runs on your PC (which has normal internet). Keep it running to stay alerted.
