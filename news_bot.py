import html
import re
import os
import time
import feedparser
import requests
from bs4 import BeautifulSoup

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
new_counts = {"bloomberg": 0, "cnbc": 0, "capital": 0, "euro2day": 0}

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
    for entry in reversed(feed.entries[:15]):
        title = html.escape(entry.title.rsplit(" - Bloomberg", 1)[0].strip())
        msg = f"<b>Bloomberg</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "bloomberg")

def fetch_cnbc():
    timestamp = int(time.time())
    rss_url = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
    proxy_url = f"https://api.allorigins.win/raw?url={rss_url}&_={timestamp}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(proxy_url, headers=headers, timeout=20)
        feed = feedparser.parse(res.content)
    except Exception as e:
        print(f"[ERROR] CNBC Proxy Fetch: {e}")
        return
        
    for entry in reversed(feed.entries[:15]):
        link = entry.link
        if link in seen_entries:
            continue
            
        title = html.escape(entry.title.strip())
        
        summary = html.escape(clean_html(entry.get("summary", "")))
        if len(summary) > 250: summary = summary[:247] + "..."
        key_points_text = f"• <i>{summary}</i>"
        
        try:
            article_res = requests.get(link, headers=headers, timeout=15)
            if article_res.status_code == 200:
                soup = BeautifulSoup(article_res.text, "html.parser")
                bullets = []
                key_points_containers = soup.find_all(class_=re.compile("KeyPoints", re.IGNORECASE))
                
                for container in key_points_containers:
                    items = container.find_all("li")
                    for item in items:
                        safe_text = html.escape(item.get_text(strip=True))
                        formatted_bullet = f"• <i>{safe_text}</i>"
                        if safe_text and formatted_bullet not in bullets:
                            bullets.append(formatted_bullet)
                
                if bullets:
                    key_points_text = "\n".join(bullets)
        except Exception:
            pass 

        msg = f"<b>CNBC</b>\n📌 <b>{title}</b>\n\n{key_points_text}\n\n🔗 <a href='{link}'>Link</a>"
        process_entry(link, msg, "cnbc")

def fetch_capital():
    rss_url = "https://news.google.com/rss/search?q=site:capital.gr+when:1h&hl=el&gl=GR&ceid=GR:el"
    feed = feedparser.parse(rss_url)
    
    for entry in reversed(feed.entries[:15]):
        title = entry.title.rsplit(" - Capital.gr", 1)[0].rsplit(" - capital.gr", 1)[0].strip()
        
        if "τιμές μετοχής" in title.lower() or "τιμες μετοχης" in title.lower():
            continue
            
        title = html.escape(title)
        msg = f"<b>Capital.gr</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "capital")

def fetch_euro2day():
    rss_url = "https://news.google.com/rss/search?q=site:euro2day.gr+when:1d&hl=el&gl=GR&ceid=GR:el"
    feed = feedparser.parse(rss_url)
    
    for entry in reversed(feed.entries[:15]):
        title = entry.title.rsplit(" - Euro2day", 1)[0].rsplit(" - euro2day.gr", 1)[0].strip()
        title = html.escape(title)
        
        msg = f"<b>Euro2day.gr</b>\n📌 {title}\n🔗 <a href='{entry.link}'>Link</a>"
        process_entry(entry.link, msg, "euro2day")


# --- ΕΚΤΕΛΕΣΗ ΚΑΙ ΕΛΕΓΧΟΣ ΜΗΝΥΜΑΤΩΝ ---
# 0. Αρχικό Μήνυμα Ενημέρωσης (Έντονο)
send_telegram("🚨 <b><u>ΝΕΑ ΕΠΙΚΑΙΡΟΤΗΤΑ</u></b> 🚨")

# 1. Έλεγχος των πηγών (ανά 30 λεπτά)
fetch_bloomberg()
if new_counts["bloomberg"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Bloomberg")

fetch_cnbc()
if new_counts["cnbc"] == 0:
    send_telegram("ℹ️ Όχι νέα σε CNBC")

fetch_capital()
if new_counts["capital"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Capital.gr")

fetch_euro2day()
if new_counts["euro2day"] == 0:
    send_telegram("ℹ️ Όχι νέα σε Euro2day")

# --- ΑΠΟΘΗΚΕΥΣΗ ΜΝΗΜΗΣ ---
if new_data_saved:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(seen_entries)[-500:]))
