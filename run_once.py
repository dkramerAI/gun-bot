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
                # Daniel Defense
                "daniel defense", "daniel defnse", "dan defense", "dd", "ddm4", 
                "ddm4v7", "ddm4 v7", "ddm4v5", "dd m4", "ddm7", "mk18", "mk-18", 
                "dd mk18", "daniel defense upper", "daniel defense lower", 
                "daniel defense ar", "dd ar15", "dd ar-15",
                
                # Glock 19
                "glock 19", "glock19", "glock-19", "g19", "g-19", "g19 gen5", 
                "g19 gen 5", "glock 19 gen5", "glock 19 gen 5", "g19 mos", 
                "19 mos", "glock 19 mos", "g19c", "g19x",
                
                # Glock 43X
                "glock 43x", "glock43x", "g43x", "43x", "g43x mos", "43x mos", 
                "43x rail", "g43x rail", "43x tactical", "43x fde", "43x slide", 
                "43x frame",
                
                # Sig P365
                "p365", "p 365", "sig p365", "sigsauer p365", "p365x", "p365 x", 
                "p365xl", "p365 macro", "p365 xmacro", "p365 x-macro", "365x", 
                "365 xl", "365 macro", "p365 sas", "p365 rose", "xmacro", "x-macro"
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

    # 3. Define Scraper Logic (Selenium Version)
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
        
        driver = None
        try:
            print("    Initializing Headless Chrome...")
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            print("    Navigating to page...")
            driver.get(CATEGORY_URL)
            time.sleep(5) # Wait for JS/Cloudflare
            
            content = driver.page_source
            soup = BeautifulSoup(content, 'html.parser')
            
            ad_links = soup.find_all('a', href=re.compile(r'/classifieds/firearms/ad/'))
            print(f"    Found {len(ad_links)} ads on page.")
            
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
                    
                    # Get Details using Driver (Safest)
                    try:
                        driver.get(url)
                        time.sleep(2)
                        ad_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        
                        price_tag = ad_soup.find('span', class_='price_val')
                        price = f"${price_tag.get_text().strip()}" if price_tag else "N/A"
                        
                        # 1. Check Timestamp
                        posted_text = ad_soup.find(string=re.compile(r'Posted:\s*'))
                        time_str = "Unknown"
                        if posted_text:
                            time_str = posted_text.strip().replace('Posted:', '').strip()
                            
                        # 2. Location
                        location = "Unknown"
                        region_tag = ad_soup.find('span', class_='region')
                        if region_tag:
                            location = region_tag.get_text().strip()
                        else:
                            loc_header = ad_soup.find('h2', string='Location')
                            if loc_header:
                                location = loc_header.find_next(string=True).strip()

                        # 3. Description
                        description = "No description available."
                        desc_div = ad_soup.find('div', class_='dj-item-description')
                        if not desc_div:
                                desc_div = ad_soup.find('div', class_='description')
                        
                        if desc_div:
                            description = desc_div.get_text(separator=' ', strip=True)[:500] + "..."

                        # 4. Send Notification (Rich Format)
                        msg = (
                            f"🚨 <b>GUN ALERT</b> 🚨\n\n"
                            f"<b>Title:</b> {title}\n"
                            f"<b>Price:</b> {price}\n"
                            f"<b>Location:</b> {location}\n"
                            f"<b>Posted:</b> {time_str}\n\n"
                            f"📝 <b>Description:</b>\n<i>{description}</i>\n\n"
                            f"📞 <b>Contact:</b> <a href='{url}'>Click to View Contact Info</a>\n\n"
                            f"🔗 <a href='{url}'><b>OPEN ADVERTISEMENT</b></a>"
                        )
                        
                        send_telegram_safe(msg)
                        seen_ads.add(ad_id)
                        new_ads_found += 1
                        
                        # Go back or just continue (next loop will get new url)
                        
                    except Exception as e:
                        print(f"[-] Detail error: {e}")
            
            # Save Seen Ads
            with open(SEEN_ADS_FILE, 'w') as f:
                json.dump(list(seen_ads), f)
                
            print(f"[*] Check complete. {new_ads_found} new ads.")
            
            if len(ad_links) == 0:
                 send_telegram_safe("⚠️ <b>WARNING:</b> Selenium found 0 ads. Page might be empty or blocked.")
            
        except Exception as e:
            err = f"⚠️ <b>ERROR:</b> Selenium Failed!\n\n<code>{str(e)}</code>"
            print(f"[-] {err}")
            send_telegram_safe(err)
            sys.exit(1)
        finally:
            if driver:
                driver.quit()

    # 4. Execute
    check_for_guns()

if __name__ == "__main__":
    main()
