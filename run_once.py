import sys
import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

# --- FAIL-SAFE CONFIGURATION ---
CONFIG_FILE = 'config.json'
SEEN_ADS_FILE = 'seen_ads.json'
BASE_URL = "https://gunsarizona.com"
CATEGORY_URL = "https://gunsarizona.com/classifieds-search?se=1&se_cats=23&days_l=1"

def get_config_safe():
    """Load config from Env Vars (GitHub) or File (Local) without external deps."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if token and chat_id:
        return {
            'telegram_bot_token': token,
            'telegram_chat_id': chat_id,
            'keywords': [
                "daniel defense", "dd", "ddm4", "ddm7", "mk18",
                "glock 19", "glock19", "g19", "glock 19 gen 5", "glock 19 gen5",
                "glock 43x", "glock43x", "g43x", "43x",
                "p365", "365", "p365x", "p365 macro", "p365 x-macro", "p365 xmacro",
                "sig p365", "sig sauer p365", "365x macro", "x-macro", "xmacro"
            ]
        }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[-] Config Load Error: {e}")
        return None

def send_telegram_safe(message):
    """Send Telegram message using ONLY standard libraries (urllib). Fail-safe."""
    config = get_config_safe()
    if not config:
        print("[-] Cannot send Telegram: No config found.")
        return

    token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=encoded_data, method='POST')
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("[+] Telegram message sent (Native Mode).")
            else:
                print(f"[-] Telegram Failed: {response.status}")
    except Exception as e:
        print(f"[-] Telegram Error (Native): {e}")

# --- MAIN LOGIC ---
def main():
    print("[-] SCRIPT STARTED - INITIALIZING...")
    
    # 1. Send Immediate Startup Message (Zero Dependencies)
    try:
        send_telegram_safe("⚠️ <b>STATUS:</b> Bot Starting...")
    except Exception:
        pass # Don't crash if this fails, just try to continue

    # 2. Import Heavy Dependencies
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        print("[+] Dependencies imported successfully.")
    except ImportError as e:
        err_msg = f"⛔ <b>CRITICAL ERROR:</b> Import Failed!\n\n<code>{str(e)}</code>"
        print(f"[-] {err_msg}")
        send_telegram_safe(err_msg)
        sys.exit(1)

    # 3. Define Scraper Logic (Now that imports are safe)
    def check_for_guns():
        print(f"[*] Checking for firearms at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        config = get_config_safe()
        
        # Load Seen Ads
        seen_ads = set()
        if os.path.exists(SEEN_ADS_FILE):
            try:
                with open(SEEN_ADS_FILE, 'r') as f:
                    seen_ads = set(json.load(f))
            except:
                pass

        keywords = [k.lower() for k in config.get('keywords', [])]
        
        # Headers to look like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            response = requests.get(CATEGORY_URL, headers=headers, timeout=30)
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
                
            soup = BeautifulSoup(response.content, 'html.parser')
            ad_links = soup.find_all('a', href=re.compile(r'/classifieds/firearms/ad/'))
            
            new_ads_found = 0
            
            for link in ad_links:
                title = link.get_text().strip()
                url = link['href']
                if not url.startswith('http'):
                    url = BASE_URL + url
                
                ad_id = url.split('-')[-1]
                
                if ad_id in seen_ads:
                    continue
                    
                if any(keyword in title.lower() for keyword in keywords):
                    print(f"[+] Found match: {title}")
                    
                    # Get Details
                    try:
                        ad_resp = requests.get(url, headers=headers, timeout=15)
                        ad_soup = BeautifulSoup(ad_resp.content, 'html.parser')
                        
                        price_tag = ad_soup.find('span', class_='price_val')
                        price = f"${price_tag.get_text().strip()}" if price_tag else "N/A"
                        
                        msg = (
                            f"🚨 <b>GUN ALERT</b> 🚨\n\n"
                            f"<b>Title:</b> {title}\n"
                            f"<b>Price:</b> {price}\n"
                            f"🔗 <a href='{url}'><b>OPEN AD</b></a>"
                        )
                        
                        send_telegram_safe(msg)
                        seen_ads.add(ad_id)
                        new_ads_found += 1
                        
                    except Exception as e:
                        print(f"[-] Detail error: {e}")
            
            # Save Seen Ads
            with open(SEEN_ADS_FILE, 'w') as f:
                json.dump(list(seen_ads), f)
                
            print(f"[*] Check complete. {new_ads_found} new ads.")
            
            if new_ads_found == 0:
                # Optional: Send heartbeat if nothing found? No, too spammy.
                # But if 0 ads found, maybe blocked?
                if len(ad_links) == 0:
                     send_telegram_safe("⚠️ <b>WARNING:</b> Scraper found 0 ads total. Possible IP Block.")
            
        except Exception as e:
            err = f"⚠️ <b>ERROR:</b> Scraper Failed!\n\n<code>{str(e)}</code>"
            print(f"[-] {err}")
            send_telegram_safe(err)
            sys.exit(1)

    # 4. Execute
    check_for_guns()

if __name__ == "__main__":
    main()
