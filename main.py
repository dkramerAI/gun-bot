import requests
from bs4 import BeautifulSoup
import json
import time
import schedule
import os
import re
from datetime import datetime, timedelta

# Configuration
CONFIG_FILE = 'config.json'
SEEN_ADS_FILE = 'seen_ads.json'
BASE_URL = "https://gunsarizona.com"
CATEGORY_URL = "https://gunsarizona.com/classifieds-search?se=1&se_cats=23&days_l=1"

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    # Expand keywords with common variations
    base_keywords = config.get('keywords', [])
    expanded = []
    
    for keyword in base_keywords:
        expanded.append(keyword.lower())
        
    # Add common variations
    variations = [
        "dd", "daniel defense", "ddm4", "ddm7", "mk18",
        "glock 19", "glock19", "g19", "gen 5", "gen5",
        "glock 43x", "glock43x", "g43x", "43x",
        "p365", "365", "p365x", "macro", "x-macro", "xmacro",
        "sig p365", "sig sauer p365"
    ]
    
    expanded.extend(variations)
    
    # Remove duplicates
    config['keywords'] = list(set(expanded))
    
    return config

def load_seen_ads():
    if os.path.exists(SEEN_ADS_FILE):
        with open(SEEN_ADS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_ads(seen_ads):
    with open(SEEN_ADS_FILE, 'w') as f:
        json.dump(list(seen_ads), f)

def parse_relative_time(time_str):
    """Parses strings like '2 hours ago', '5 minutes ago', '1 day ago'."""
    now = datetime.now()
    time_str = time_str.lower()
    
    try:
        if 'minute' in time_str:
            minutes = int(re.search(r'(\d+)', time_str).group(1))
            return now - timedelta(minutes=minutes)
        elif 'hour' in time_str:
            hours = int(re.search(r'(\d+)', time_str).group(1))
            return now - timedelta(hours=hours)
        elif 'day' in time_str:
            days = int(re.search(r'(\d+)', time_str).group(1))
            return now - timedelta(days=days)
        else:
            return now
    except:
        return now

def check_for_guns():
    print(f"[*] Checking for firearms at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    config = load_config()
    seen_ads = load_seen_ads()
    keywords = [k.lower() for k in config.get('keywords', [])]
    
    try:
        response = requests.get(CATEGORY_URL, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            print(f"[-] Failed to fetch page: {response.status_code}")
            return

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Finding ads
        ad_links = soup.find_all('a', href=re.compile(r'/classifieds/firearms/ad/'))
        
        new_ads_found = 0
        
        for link in ad_links:
            title = link.get_text().strip()
            url = link['href']
            if not url.startswith('http'):
                url = BASE_URL + url
            
            # Extract ID from URL (usually the last part)
            ad_id = url.split('-')[-1]
            
            # print(f"    Scanning: {title[:50]}...") # Reduce noise

            if ad_id in seen_ads:
                continue
                
            # Check keywords in title
            if any(keyword in title.lower() for keyword in keywords):
                print(f"[+] Found potential match: {title}")
                
                # Visit detail page to get details
                try:
                    ad_resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    ad_soup = BeautifulSoup(ad_resp.content, 'html.parser')
                    
                    # 1. Check Timestamp (still good to have, but we trust the search URL mostly)
                    posted_text = ad_soup.find(string=re.compile(r'Posted:\s*'))
                    time_str = "Unknown"
                    if posted_text:
                        time_str = posted_text.strip().replace('Posted:', '').strip()
                    
                    print(f"    - MATCH! Gathering details...")
                    
                    # 2. Extract Details
                    # Price
                    price = "N/A"
                    price_tag = ad_soup.find('span', class_='price_val')
                    if price_tag:
                        price = f"${price_tag.get_text().strip()}"
                        
                    # Location
                    location = "Unknown"
                    region_tag = ad_soup.find('span', class_='region')
                    if region_tag:
                        location = region_tag.get_text().strip()
                    else:
                        loc_header = ad_soup.find('h2', string='Location')
                        if loc_header:
                            location = loc_header.find_next(string=True).strip()

                    # Description
                    description = "No description available."
                    desc_div = ad_soup.find('div', class_='dj-item-description')
                    if not desc_div:
                            desc_div = ad_soup.find('div', class_='description')
                    
                    if desc_div:
                        description = desc_div.get_text(separator=' ', strip=True)[:500] + "..."

                    # 3. Send Notification (Improved Formatting)
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
                    
                    send_telegram_message(msg, config)
                    seen_ads.add(ad_id)
                    new_ads_found += 1
                        
                except Exception as e:
                    print(f"[-] Error checking ad detail {url}: {e}")
        
        save_seen_ads(seen_ads)
        print(f"[*] Check complete. {new_ads_found} new notifications sent.")

    except Exception as e:
        print(f"[-] Error during check: {e}")

def send_telegram_message(message, config):
    token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    
    if not token or not chat_id:
        print("[-] Telegram not configured.")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        response = requests.post(url, data=data)
            
        if response.status_code != 200:
            print(f"[-] Failed to send Telegram message: {response.text}")
    except Exception as e:
        print(f"[-] Error sending Telegram message: {e}")

def main():
    print("Starting GunsArizona Bot...")
    
    # Run once immediately
    check_for_guns()
    
    # Schedule
    config = load_config()
    interval = config.get('check_interval_minutes', 10)
    schedule.every(interval).minutes.do(check_for_guns)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
