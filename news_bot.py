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
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"[ERROR] Telegram API: {res.text}")
    except Exception as e:
        print(f"[ERROR] Telegram Request: {e}")

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
        # Καθαρισμός τίτλου και ασφαλής μορφοποίηση για το Telegram (π.χ. σύμβολα & ή <)
        title = html.escape(entry.title.rsplit(" - Bloomberg", 1)[0].strip())
        msg = f"<b>Bloomberg</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg)

def fetch_cnbc():
    feed = feedparser.parse("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for entry in reversed(feed.entries[:10]):
        link = entry.link
        
        # Αν το έχουμε ήδη στείλει, προχωράμε στο επόμενο χωρίς να κάνουμε άδικα scraping
        if link in seen_entries:
            continue
            
        title = html.escape(entry.title.strip())
        
        try:
            # Μπαίνει μέσα στο άρθρο για να βρει τα Key Points
            res = requests.get(link, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Ψάχνει την κλάση που βάζει το CNBC στα Key Points
            key_points_container = soup.find(class_=re.compile("KeyPoints", re.IGNORECASE))
            bullets = []
            
            if key_points_container:
                items = key_points_container.find_all("li")
                for item in items:
                    safe_text = html.escape(item.get_text(strip=True))
                    bullets.append(f"• <i>{safe_text}</i>")
            
            # Αν βρήκε Key Points τα ενώνει, αλλιώς βάζει την απλή περίληψη ως backup
            if bullets:
                key_points_text = "\n".join(bullets)
            else:
                summary = html.escape(clean_html(entry.get("summary", "")))
                if len(summary) > 250: summary = summary[:247] + "..."
                key_points_text = f"• <i>{summary}</i>"

            # Μήνυμα ΧΩΡΙΣ το Link, μόνο τίτλος και Key points
            msg = f"<b>CNBC</b>\n📌 <b>{title}</b>\n\n{key_points_text}"
            process_entry(link, msg)
            
        except Exception as e:
            print(f"[ERROR] CNBC Scraping: {e}")

def fetch_capital():
    feed = feedparser.parse("https://www.capital.gr/rss")
    for entry in reversed(feed.entries[:10]):
        title = html.escape(entry.title.strip())
        msg = f"<b>Capital.gr</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg)

def fetch_forex_factory():
    url = "https://www.forexfactory.com/news/hot"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        articles = soup.find_all("a", href=re.compile(r"^/news/\d+"))
        unique_links = {}
        for a in articles:
            link = "https://www.forexfactory.com" + a['href']
            title = html.escape(a.get_text(strip=True))
            if title and len(title) > 10:
                unique_links[link] = title
                
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
