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

# Φόρτωση χρονομέτρων (Για το Forex)
if os.path.exists(TIMERS_FILE):
    with open(TIMERS_FILE, "r", encoding="utf-8") as f:
        timers = json.load(f)
else:
    timers = {"forex": 0}

new_data_saved = False
new_counts = {"bloomberg": 0, "cnbc": 0, "capital": 0, "forex": 0}

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True  # Αυτό απενεργοποιεί τη μεγάλη εικόνα του άρθρου
    }
    try:
        requests.post(url, json=payload, timeout=10)
        time.sleep(0.5)
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
        new_counts[source] += 1
        send_telegram(msg)

def fetch_bloomberg():
    feed = feedparser.parse("https://news.google.com/rss/search?q=site:bloomberg.com+when:1h&hl=en-US&gl=US&ceid=US:en")
    for entry in reversed(feed.entries[:10]):
        title = html.escape(entry.title.rsplit(" - Bloomberg", 1)[0].strip())
        msg = f"<b>Bloomberg</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "bloomberg")

def fetch_cnbc():
    # Χρησιμοποιούμε το RSS ID 15839069 (Latest News)
    feed = feedparser.parse("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    
    for entry in reversed(feed.entries[:15]):
        link = entry.link
        if link in seen_entries:
            continue
            
        title = html.escape(entry.title.strip())
        
        # Default περίληψη αν κάτι πάει στραβά
        summary = html.escape(clean_html(entry.get("summary", "")))
        if len(summary) > 250: summary = summary[:247] + "..."
        key_points_text = f"• <i>{summary}</i>"
        
        try:
            res = requests.get(link, headers=headers, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                
                bullets = []
                # Ψάχνουμε ΟΛΑ τα containers που περιέχουν τη λέξη KeyPoints 
                key_points_containers = soup.find_all(class_=re.compile("KeyPoints", re.IGNORECASE))
                
                for container in key_points_containers:
                    items = container.find_all("li")
                    for item in items:
                        safe_text = html.escape(item.get_text(strip=True))
                        # Προσθήκη μόνο αν δεν είναι κενό και δεν έχει ήδη μπει (αποφυγή διπλότυπων)
                        formatted_bullet = f"• <i>{safe_text}</i>"
                        if safe_text and formatted_bullet not in bullets:
                            bullets.append(formatted_bullet)
                
                # Αν βρήκε τα Key Points, τα βάζει όλα
                if bullets:
                    key_points_text = "\n".join(bullets)
                    
        except Exception as e:
            print(f"[WARNING] CNBC Scraping failed for {link}: {e}")

        # Αποστολή μηνύματος με ΟΛΑ τα Key points και το Link στο τέλος
        msg = f"<b>CNBC</b>\n📌 <b>{title}</b>\n\n{key_points_text}\n\n🔗 <a href='{link}'>Link</a>"
        process_entry(link, msg, "cnbc")
def fetch_capital():
    # Παράκαμψη του firewall χρησιμοποιώντας το Google News
    rss_url = "https://news.google.com/rss/search?q=site:capital.gr+when:1h&hl=el&gl=GR&ceid=GR:el"
    feed = feedparser.parse(rss_url)
    
    for entry in reversed(feed.entries[:15]):
        # Καθαρισμός του τίτλου από τις ετικέτες του Google
        title = entry.title.rsplit(" - Capital.gr", 1)[0].rsplit(" - capital.gr", 1)[0].strip()
        
        # ΦΙΛΤΡΟ: Αν ο τίτλος μιλάει για απλές τιμές μετοχών, τον προσπερνάμε!
        if "τιμές μετοχής" in title.lower() or "τιμες μετοχης" in title.lower():
            continue
            
        title = html.escape(title)
        
        msg = f"<b>Capital.gr</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "capital")

def fetch_forex_factory():
    # Χρησιμοποιούμε AllOrigins Proxy με timestamp για να σπάσουμε την προσωρινή 
    # μνήμη (cache) και το firewall του Cloudflare που μπλοκάρει το GitHub!
    timestamp = int(time.time())
    proxy_url = f"https://api.allorigins.win/raw?url=https://www.forexfactory.com/news/hot&_={timestamp}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(proxy_url, headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Ψάχνουμε τα links που οδηγούν στα άρθρα (/news/...)
        articles = soup.find_all("a", href=re.compile(r"^/news/\d+"))
        unique_links = {}
        
        for a in articles:
            link = "https://www.forexfactory.com" + a['href']
            title = html.escape(a.get_text(strip=True))
            
            # Αγνοούμε κενά ή τα links που οδηγούν στα σχόλια (π.χ. "167 comments")
            if title and len(title) > 10 and "comments" not in title.lower():
                unique_links[link] = title
                
        for link, title in reversed(list(unique_links.items())[:10]):
            msg = f"🔴 <b>Forex Factory (Hot News)</b>\n📌 {title}\n\n🔗 <a href='{link}'>Link</a>"
            process_entry(link, msg, "forex")
            
    except Exception as e:
        print(f"[ERROR] Forex Factory: {e}")


# --- ΕΚΤΕΛΕΣΗ ΚΑΙ ΕΛΕΓΧΟΣ ΜΗΝΥΜΑΤΩΝ ---
current_time = time.time()

# 0. Αρχικό Μήνυμα Ενημέρωσης
send_telegram("------- ΝΕΑ ΕΠΙΚΑΙΡΟΤΗΤΑ -------")

# 1. Bloomberg, CNBC, Capital (Ανά 30 λεπτά)
fetch_bloomberg()
if new_counts["bloomberg"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Bloomberg")

fetch_cnbc()
if new_counts["cnbc"] == 0:
    send_telegram("ℹ️ Όχι νέα σε CNBC")

fetch_capital()
if new_counts["capital"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Capital.gr")

# 2. Forex Factory (Ανά 1 ώρα = 3500 δευτερόλεπτα)
forex_checked = False
if current_time - timers.get("forex", 0) >= 3500:
    forex_checked = True
    fetch_forex_factory()
    timers["forex"] = current_time
    new_data_saved = True

if forex_checked and new_counts["forex"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Forex Factory")

# --- ΑΠΟΘΗΚΕΥΣΗ ΜΝΗΜΗΣ & ΧΡΟΝΟΜΕΤΡΩΝ ---
if new_data_saved:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
    with open(TIMERS_FILE, "w", encoding="utf-8") as f:
        json.dump(timers, f)
