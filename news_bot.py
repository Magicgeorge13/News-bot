import html
import re
import os
import feedparser
import requests
from bs4 import BeautifulSoup

# Παίρνει τους κωδικούς από τα Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen.txt"

# Διαβάζει το αρχείο μνήμης
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
        print(f"[ERROR] Telegram: {e}")

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
    # Αντλούμε τα νέα απευθείας από το tab "Hot News"
    url = "https://www.forexfactory.com/news/hot"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Το Forex Factory βάζει τα links των ειδήσεων σε μορφή /news/12345-titlos
        # Ψάχνουμε όλα τα <a> tags που ταιριάζουν σε αυτό το μοτίβο
        articles = soup.find_all("a", href=re.compile(r"^/news/\d+"))
        
        # Παίρνουμε τα 10 πιο πρόσφατα (αφαιρώντας τα διπλότυπα links της ίδιας σελίδας)
        unique_links = {}
        for a in articles:
            link = "https://www.forexfactory.com" + a['href']
            title = a.get_text(strip=True)
            if title and len(title) > 10: # Αγνοούμε κενά εικονίδια
                unique_links[link] = title
                
        # Μετατροπή σε λίστα και αντιστροφή για να στείλει τα παλαιότερα πρώτα
        for link, title in reversed(list(unique_links.items())[:10]):
            msg = f"🔴 <b>Forex Factory (Hot News)</b>\n📌 {title}\n🔗 <a href='{link}'>Link</a>"
            process_entry(link, msg)
            
    except Exception as e:
        print(f"[ERROR] Forex Factory: {e}")

# Εκτέλεση ελέγχων
fetch_bloomberg()
fetch_cnbc()
fetch_capital()
fetch_forex_factory()

# Ενημέρωση μνήμης
if new_entries_added:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
