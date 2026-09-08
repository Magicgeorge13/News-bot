import html
import re
import os
import feedparser
import requests

# Παίρνει τους κωδικούς από τα Secrets που φτιάξαμε
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen.txt"

# Διαβάζει το αρχείο μνήμης για να μην στείλει τα ίδια
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_entries = set(f.read().splitlines())
else:
    seen_entries = set()

new_entries_added = False

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] {e}")

def clean_html(raw_html: str) -> str:
    clean_text = re.sub(r"<.*?>", "", raw_html)
    return html.unescape(clean_text).strip()

def process_entry(unique_id, msg):
    global new_entries_added
    if unique_id not in seen_entries:
        seen_entries.add(unique_id)
        new_entries_added = True
        send_telegram(msg)

def fetch_bloomberg():
    feed = feedparser.parse("https://news.google.com/rss/search?q=site:bloomberg.com+when:1h&hl=en-US&gl=US&ceid=US:en")
    for entry in reversed(feed.entries[:10]):
        title = entry.title.rsplit(" - Bloomberg", 1)[0].strip()
        msg = f"<b>Bloomberg</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg)

def fetch_cnbc():
    feed = feedparser.parse("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664")
    for entry in reversed(feed.entries[:10]):
        summary = clean_html(entry.get("summary", ""))
        if len(summary) > 200: summary = summary[:197] + "..."
        msg = f"<b>CNBC</b>\n📌 <b>{entry.title.strip()}</b>\n📝 <i>{summary}</i>\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg)

def fetch_capital():
    feed = feedparser.parse("https://www.capital.gr/rss")
    for entry in reversed(feed.entries[:10]):
        msg = f"<b>Capital.gr</b>\n📌 {entry.title.strip()}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg)

def fetch_forex_factory():
    try:
        res = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        events = res.json()
    except:
        return
    for ev in events:
        if ev.get("impact") == "High":
            unique_id = f"{ev.get('country')}_{ev.get('title')}_{ev.get('date')}"
            msg = f"🔴 <b>Forex Factory</b>\n📌 {ev.get('country')}: {ev.get('title')}"
            process_entry(unique_id, msg)

# Τρέχουμε τις λειτουργίες
fetch_bloomberg()
fetch_cnbc()
fetch_capital()
fetch_forex_factory()

# Αν βρήκε νέα, ενημερώνει το αρχείο μνήμης (κρατάει τα τελευταία 500 για να μη βαρύνει)
if new_entries_added:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
