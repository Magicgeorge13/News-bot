import html
import os
import time
import feedparser
import requests

# Παίρνει τους κωδικούς από τα Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen.txt"

# Φόρτωση μνήμης 
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_entries = set(f.read().splitlines())
else:
    seen_entries = set()

new_data_saved = False
new_counts = {"bloomberg": 0, "capital": 0, "mononews": 0}

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
        time.sleep(0.5)
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def process_entry(unique_id, msg, source):
    global new_data_saved
    if unique_id not in seen_entries:
        seen_entries.add(unique_id)
        new_data_saved = True
        new_counts[source] += 1
        send_telegram(msg)

def fetch_bloomberg():
    feed = feedparser.parse("https://news.google.com/rss/search?q=site:bloomberg.com+when:1h&hl=en-US&gl=US&ceid=US:en")
    for entry in reversed(feed.entries[:15]):
        title = html.escape(entry.title.rsplit(" - Bloomberg", 1)[0].strip())
        msg = f"🌎 <a href='https://www.bloomberg.com'><b>#Bloomberg</b></a>\n▫️ {title}\n\n🔗 <a href='{entry.link}'>Άρθρο</a>"
        process_entry(entry.link, msg, "bloomberg")

def fetch_capital():
    rss_url = "https://news.google.com/rss/search?q=site:capital.gr+when:1h&hl=el&gl=GR&ceid=GR:el"
    feed = feedparser.parse(rss_url)
    
    for entry in reversed(feed.entries[:15]):
        title = entry.title.rsplit(" - Capital.gr", 1)[0].rsplit(" - capital.gr", 1)[0].strip()
        
        # Φίλτρο για να μην παίρνουμε τις σκέτες "τιμές μετοχής"
        if "τιμές μετοχής" in title.lower() or "τιμες μετοχης" in title.lower():
            continue
            
        title = html.escape(title)
        msg = f"🏛️ <a href='https://www.capital.gr'><b>#Capital</b></a>\n▫️ {title}\n\n🔗 <a href='{entry.link}'>Άρθρο</a>"
        process_entry(entry.link, msg, "capital")

def fetch_mononews():
    rss_url = "https://news.google.com/rss/search?q=site:mononews.gr+when:1h&hl=el&gl=GR&ceid=GR:el"
    feed = feedparser.parse(rss_url)
    
    for entry in reversed(feed.entries[:15]):
        title = entry.title.rsplit(" - mononews", 1)[0].rsplit(" - Mononews", 1)[0].strip()
        title = html.escape(title)
        
        msg = f"📊 <a href='https://www.mononews.gr'><b>#Mononews</b></a>\n▫️ {title}\n\n🔗 <a href='{entry.link}'>Άρθρο</a>"
        process_entry(entry.link, msg, "mononews")


# --- ΕΚΤΕΛΕΣΗ ΚΑΙ ΕΛΕΓΧΟΣ ΜΗΝΥΜΑΤΩΝ ---
send_telegram("🚨 <b><u>ΝΕΑ ΕΠΙΚΑΙΡΟΤΗΤΑ</u></b> 🚨")

fetch_bloomberg()
if new_counts["bloomberg"] == 0:
    send_telegram("🔕 <i>Όχι νέα σε Bloomberg</i>")

fetch_capital()
if new_counts["capital"] == 0:
    send_telegram("🔕 <i>Όχι νέα σε Capital.gr</i>")

fetch_mononews()
if new_counts["mononews"] == 0:
    send_telegram("🔕 <i>Όχι νέα σε Mononews.gr</i>")
    
# --- ΑΠΟΘΗΚΕΥΣΗ ΜΝΗΜΗΣ ---
if new_data_saved:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
