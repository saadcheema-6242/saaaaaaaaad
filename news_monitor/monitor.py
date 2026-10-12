"""Greece-appointment news monitor (Option A).

Watches the GVC World (Pakistan-Greece) and Greek Embassy Islamabad news pages
and alerts the moment a NEW announcement appears:

  - sends an email once per new item, and
  - shows a desktop popup that re-appears every minute until you tick "Got it".

News only. It does NOT touch the booking scheduler and does NOT book anything.

Run:
    python monitor.py            # start monitoring (24/7 loop)
    python monitor.py --test     # fetch once, print what it sees, exit
    python monitor.py --test-email   # send a test email and exit

Config lives in config.json next to this file (copy config.example.json).
"""

import argparse
import json
import logging
import os
import queue
import re
import smtplib
import ssl
import sys
import threading
import time
import webbrowser
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Missing dependency 'requests'. Run:  pip install -r requirements.txt")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    HAVE_BS4 = True
except ImportError:
    HAVE_BS4 = False  # a regex fallback is used instead

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
STATE_PATH = os.path.join(HERE, "seen.json")
LOG_PATH = os.path.join(HERE, "monitor.log")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("monitor")


# --------------------------------------------------------------------------- #
# config / state
# --------------------------------------------------------------------------- #
def load_config():
    if not os.path.exists(CONFIG_PATH):
        log.error("No config.json found. Copy config.example.json to config.json and edit it.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.warning("Could not save state: %s", e)


# --------------------------------------------------------------------------- #
# fetch + parse
# --------------------------------------------------------------------------- #
def fetch(url):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"}, timeout=25)
            if r.status_code == 200 and r.text:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(2 * (attempt + 1))
    log.warning("Fetch failed for %s (%s)", url, last)
    return None


def extract_items(html, base_url, match):
    """Return {absolute_url: title} for anchors whose href contains `match`."""
    items = {}
    if HAVE_BS4:
        soup = BeautifulSoup(html, "html.parser")
        anchors = [(a.get("href", ""), a.get_text(" ", strip=True)) for a in soup.find_all("a")]
    else:
        anchors = []
        for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
            text = re.sub(r"<[^>]+>", " ", m.group(2))
            anchors.append((m.group(1), re.sub(r"\s+", " ", text).strip()))
    for href, text in anchors:
        if not href or match.lower() not in href.lower():
            continue
        title = re.sub(r"\s+", " ", (text or "")).strip()
        if len(title) < 5:
            continue
        url = urljoin(base_url, href)
        # keep the first (usually longest/real) title seen for a url
        items.setdefault(url, title)
    return items


def matches_keywords(title, keywords):
    t = title.lower()
    return any(k.lower() in t for k in keywords)


# --------------------------------------------------------------------------- #
# email
# --------------------------------------------------------------------------- #
def send_email(cfg, subject, body):
    e = cfg.get("email", {})
    if not e.get("enabled"):
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = e.get("from") or e.get("username")
    to = e.get("to") or []
    if isinstance(to, str):
        to = [to]
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    port = int(e.get("smtp_port", 465))
    host = e.get("smtp_host", "smtp.gmail.com")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
                s.login(e["username"], e["app_password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(e["username"], e["app_password"])
                s.send_message(msg)
        log.info("Email sent: %s", subject)
    except Exception as ex:
        log.error("Email failed: %s", ex)


# --------------------------------------------------------------------------- #
# desktop popup (Tkinter, main thread) — re-shows until acknowledged
# --------------------------------------------------------------------------- #
class Notifier:
    """Runs on the main thread. Pops a window that lists unacknowledged news
    items and re-raises itself every `renotify` seconds until each is ticked."""

    def __init__(self, cfg, inbox):
        self.cfg = cfg
        self.inbox = inbox                       # queue of new items from worker
        self.active = {}                         # url -> {title, source}
        self.renotify_ms = int(cfg.get("renotify_seconds", 60)) * 1000
        self.sound = cfg.get("sound", True)
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.win = None
        self.root.after(1000, self._poll_inbox)
        self.root.after(self.renotify_ms, self._renotify)

    def run(self):
        self.root.mainloop()

    def _poll_inbox(self):
        changed = False
        try:
            while True:
                item = self.inbox.get_nowait()
                self.active[item["url"]] = {"title": item["title"], "source": item["source"]}
                changed = True
        except queue.Empty:
            pass
        if changed:
            self._show(beep=True)
        self.root.after(1000, self._poll_inbox)

    def _renotify(self):
        if self.active:
            self._show(beep=True)
        self.root.after(self.renotify_ms, self._renotify)

    def _beep(self):
        if not self.sound:
            return
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

    def _ack(self, url):
        self.active.pop(url, None)
        if self.active:
            self._show(beep=False)
        elif self.win is not None:
            self.win.destroy()
            self.win = None

    def _show(self, beep):
        tk = self.tk
        if self.win is None or not self.win.winfo_exists():
            self.win = tk.Toplevel(self.root)
            self.win.title("Greece appointment news")
            self.win.configure(bg="#111418")
            self.win.protocol("WM_DELETE_WINDOW", lambda: None)  # must tick to dismiss
        w = self.win
        for child in w.winfo_children():
            child.destroy()

        tk.Label(w, text="🛂  New Greece-appointment news", font=("Segoe UI", 13, "bold"),
                 fg="#ffffff", bg="#111418").pack(anchor="w", padx=16, pady=(14, 8))

        for url, info in list(self.active.items()):
            row = tk.Frame(w, bg="#1b1f26")
            row.pack(fill="x", padx=12, pady=5)
            tk.Label(row, text=info["source"], font=("Segoe UI", 8), fg="#8aa0c0",
                     bg="#1b1f26").pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(row, text=info["title"], font=("Segoe UI", 10, "bold"), fg="#eceef2",
                     bg="#1b1f26", wraplength=430, justify="left").pack(anchor="w", padx=10)
            btns = tk.Frame(row, bg="#1b1f26")
            btns.pack(anchor="e", padx=10, pady=8)
            tk.Button(btns, text="Open", command=lambda u=url: webbrowser.open(u)).pack(side="left", padx=4)
            tk.Button(btns, text="✓ Got it", command=lambda u=url: self._ack(u),
                      bg="#2457f5", fg="#ffffff").pack(side="left", padx=4)

        if len(self.active) > 1:
            tk.Button(w, text="✓ Got it (all)", command=lambda: [self._ack(u) for u in list(self.active)],
                      bg="#2457f5", fg="#ffffff").pack(pady=(4, 14))
        else:
            tk.Frame(w, bg="#111418", height=8).pack()

        w.update_idletasks()
        w.geometry(f"+{w.winfo_screenwidth() - w.winfo_width() - 40}+60")
        w.deiconify()
        w.lift()
        w.attributes("-topmost", True)
        if beep:
            self._beep()


# --------------------------------------------------------------------------- #
# worker loop
# --------------------------------------------------------------------------- #
def check_once(cfg, state, inbox=None, announce=True):
    """Fetch every source, detect new items. Returns list of new items.
    announce=False (first run) just records a baseline silently."""
    new_items = []
    kw = cfg.get("keywords", [])
    kw_only = cfg.get("keywords_only", False)
    for src in cfg["sources"]:
        name, url, match = src["name"], src["url"], src.get("match", "/news/")
        html = fetch(url)
        if not html:
            continue
        found = extract_items(html, url, match)
        seen = set(state.get(url, []))
        first_run = url not in state
        for link, title in found.items():
            if link in seen:
                continue
            seen.add(link)
            if first_run:
                continue  # baseline existing items silently
            if kw_only and not matches_keywords(title, kw):
                continue
            item = {"url": link, "title": title, "source": name,
                    "hot": matches_keywords(title, kw)}
            new_items.append(item)
        state[url] = sorted(seen)
        if first_run:
            log.info("Baseline: %s — recorded %d existing item(s).", name, len(found))
    save_state(state)

    if announce:
        for it in new_items:
            tag = " [MATCHES KEYWORD]" if it["hot"] else ""
            log.info("NEW: [%s] %s%s  %s", it["source"], it["title"], tag, it["url"])
            subject = f"Greece appointment news: {it['title']}"
            body = (f"New announcement on {it['source']}:\n\n{it['title']}\n{it['url']}\n\n"
                    f"Detected {datetime.now():%Y-%m-%d %H:%M}.\n\n-- Greece news monitor")
            send_email(cfg, subject, body)
            if inbox is not None:
                inbox.put(it)
    return new_items


def worker(cfg, inbox, stop):
    state = load_state()
    first = not state
    news = check_once(cfg, state, inbox=inbox, announce=not first)
    if first:
        log.info("First run complete — baseline saved. You'll be alerted on NEW posts from now on.")
    interval = int(cfg.get("check_interval_seconds", 120))
    while not stop.is_set():
        if stop.wait(interval):
            break
        try:
            check_once(cfg, state, inbox=inbox, announce=True)
        except Exception as e:
            log.error("Check error: %s", e)


# --------------------------------------------------------------------------- #
# entry
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="fetch once, print detected items, exit")
    ap.add_argument("--test-email", action="store_true", help="send a test email and exit")
    args = ap.parse_args()
    cfg = load_config()

    if args.test_email:
        send_email(cfg, "Greece news monitor — test email",
                   "If you can read this, email alerts are working.")
        return

    if args.test:
        state = {}
        for src in cfg["sources"]:
            html = fetch(src["url"])
            print(f"\n=== {src['name']} ({src['url']}) ===")
            if not html:
                print("  (could not fetch — check the URL / your internet)")
                continue
            items = extract_items(html, src["url"], src.get("match", "/news/"))
            if not items:
                print("  (no news links found — the page may need JavaScript; tell Claude)")
            for url, title in list(items.items())[:20]:
                print(f"  - {title}\n    {url}")
        return

    log.info("Starting monitor. Checking every %ss. Sources: %s",
             cfg.get("check_interval_seconds", 120), ", ".join(s["name"] for s in cfg["sources"]))
    inbox = queue.Queue()
    stop = threading.Event()
    use_popup = cfg.get("desktop_popup", True)

    if use_popup:
        try:
            notifier = Notifier(cfg, inbox)
        except Exception as e:
            log.warning("Desktop popups unavailable (%s). Continuing with email only.", e)
            use_popup = False

    t = threading.Thread(target=worker, args=(cfg, inbox, stop), daemon=True)
    t.start()

    try:
        if use_popup:
            notifier.run()          # blocks on Tkinter mainloop
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        log.info("Monitor stopped.")


if __name__ == "__main__":
    main()
