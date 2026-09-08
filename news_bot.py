import html
import re
import os
import time
import json
import feedparser
import requests
from bs4 import BeautifulSoup

# Παίρνει τους κωδικούς από τα Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen.txt"
TIMERS_FILE = "timers.json"

# Φόρτωση μνήμης 
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_entries = set(f.read().splitlines())
else:
    seen_entries = set()

# Φόρτωση χρονομέτρων (Πλέον το χρειαζόμαστε μόνο για το Forex)
if os.path.exists(TIMERS_FILE):
    with open(TIMERS_FILE, "r", encoding="utf-8") as f:
        timers = json.load(f)
else:
    timers = {"forex": 0}

new_data_saved = False

# Μετρητής για το αν βρέθηκαν νέα σε αυτό το run
new_counts = {"bloomberg": 0, "cnbc": 0, "capital": 0, "forex": 0}

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        time.sleep(0.5) # Μικρή παύση για να μην μας μπλοκάρει το Telegram από το σπαμ
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def clean_html(raw_html: str) -> str:
    clean_text = re.sub(r"<.*?>", "", raw_html)
    return html.unescape(clean_text).strip()

def process_entry(unique_id, msg, source):
    global new_data_saved
    if unique_id not in seen_entries:
        seen_entries.add(unique_id)
        new_data_saved = True
        new_counts[source] += 1  # Καταγράφει ότι βρέθηκε νέο άρθρο
        send_telegram(msg)

def fetch_bloomberg():
    feed = feedparser.parse("https://news.google.com/rss/search?q=site:bloomberg.com+when:1h&hl=en-US&gl=US&ceid=US:en")
    for entry in reversed(feed.entries[:10]):
        title = html.escape(entry.title.rsplit(" - Bloomberg", 1)[0].strip())
        msg = f"<b>Bloomberg</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "bloomberg")

def fetch_cnbc():
    feed = feedparser.parse("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for entry in reversed(feed.entries[:10]):
        link = entry.link
        if link in seen_entries:
            continue
            
        title = html.escape(entry.title.strip())
        try:
            res = requests.get(link, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            key_points_container = soup.find(class_=re.compile("KeyPoints", re.IGNORECASE))
            bullets = []
            
            if key_points_container:
                items = key_points_container.find_all("li")
                for item in items:
                    safe_text = html.escape(item.get_text(strip=True))
                    bullets.append(f"• <i>{safe_text}</i>")
            
            if bullets:
                key_points_text = "\n".join(bullets)
            else:
                summary = html.escape(clean_html(entry.get("summary", "")))
                if len(summary) > 250: summary = summary[:247] + "..."
                key_points_text = f"• <i>{summary}</i>"

            msg = f"<b>CNBC</b>\n📌 <b>{title}</b>\n\n{key_points_text}"
            process_entry(link, msg, "cnbc")
        except Exception:
            pass

def fetch_capital():
    # Χρήση του rss2json API που ξεπερνάει τα firewalls και μας δίνει την αυθεντική ροή
    api_url = "https://api.rss2json.com/v1/api.json?rss_url=https://www.capital.gr/rss"
    try:
        res = requests.get(api_url, timeout=15)
        data = res.json()
        
        if data.get("status") == "ok":
            items = data.get("items", [])
            # Ελέγχουμε τις 15 πιο πρόσφατες γρήγορες ειδήσεις
            for entry in reversed(items[:15]):
                title = html.escape(entry.get("title", "").strip())
                link = entry.get("link", "")
                
                msg = f"<b>Capital.gr</b>\n📌 {title}\n🔗 <a href='{link}'>Link</a>"
                process_entry(link, msg, "capital")
        else:
            print(f"[ERROR] Capital.gr API: {data.get('message')}")
    except Exception as e:
        print(f"[ERROR] Capital.gr: {e}")

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
            process_entry(link, msg, "forex")
    except Exception:
        pass


# --- ΕΚΤΕΛΕΣΗ ΚΑΙ ΕΛΕΓΧΟΣ ΜΗΝΥΜΑΤΩΝ ---
current_time = time.time()

# 1. Bloomberg, CNBC, Capital (Ανά 30 λεπτά - τρέχουν σε κάθε κύκλο)
fetch_bloomberg()
if new_counts["bloomberg"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Bloomberg")

fetch_cnbc()
if new_counts["cnbc"] == 0:
    send_telegram("ℹ️ Όχι νέα σε CNBC")

fetch_capital()
if new_counts["capital"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Capital.gr")

# 2. Forex Factory (Τρέχει ΜΟΝΟ αν έχουν περάσει 2 ώρες)
forex_checked = False
if current_time - timers.get("forex", 0) >= 7100:
    forex_checked = True
    fetch_forex_factory()
    timers["forex"] = current_time
    new_data_saved = True

# Αν ελέγχθηκε το Forex Factory και δεν είχε νέα, στείλε ειδοποίηση
if forex_checked and new_counts["forex"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Forex Factory")


# --- ΑΠΟΘΗΚΕΥΣΗ ΜΝΗΜΗΣ & ΧΡΟΝΟΜΕΤΡΩΝ ---
if new_data_saved:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
    with open(TIMERS_FILE, "w", encoding="utf-8") as f:
        json.dump(timers, f)
