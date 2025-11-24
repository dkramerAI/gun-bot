import sys
import os

print("[-] SCRIPT STARTED - INITIALIZING...")

try:
    import requests
    from bs4 import BeautifulSoup
    import json
    import re
    from datetime import datetime, timedelta
    print("[+] Basic modules imported.")
except Exception as e:
    print(f"[-] CRITICAL: Failed to import basic modules: {e}")
    sys.exit(1)

try:
    import cloudscraper
    print("[+] Cloudscraper imported.")
    USE_CLOUDSCRAPER = True
except Exception as e:
    print(f"[-] WARNING: Cloudscraper failed to import: {e}")
    print("[-] Falling back to standard requests.")
    USE_CLOUDSCRAPER = False

def check_for_guns():
    print(f"[*] Checking for firearms at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    config = load_config()
    seen_ads = load_seen_ads()
    keywords = [k.lower() for k in config.get('keywords', [])]
    
    # Use cloudscraper if available, otherwise fallback to requests
    try:
        if USE_CLOUDSCRAPER:
            print("    Using Cloudscraper...")
            scraper = cloudscraper.create_scraper()
            response = scraper.get(CATEGORY_URL)
        else:
            print("    Using Standard Requests (Fallback)...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            response = requests.get(CATEGORY_URL, headers=headers)
            
        if response.status_code != 200:
            print(f"[-] Failed to fetch page: {response.status_code}")
            raise Exception(f"HTTP Error {response.status_code}")

    except Exception as e:
        print(f"[-] Request Failed: {e}")
        raise e

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Finding ads - be more specific to get only title links
    ad_links = soup.find_all('a', href=re.compile(r'/classifieds/firearms/ad/'))
    
    new_ads_found = 0
    
    for link in ad_links:
        title = link.get_text().strip()
        url = link['href']
        if not url.startswith('http'):
            url = BASE_URL + url
        
        # Extract ID from URL (usually the last part)
        ad_id = url.split('-')[-1]
        
        if ad_id in seen_ads:
            continue
            
        # Check keywords in title
        if any(keyword in title.lower() for keyword in keywords):
            print(f"[+] Found potential match: {title}")
            
            # Visit detail page to get details
            try:
                if USE_CLOUDSCRAPER:
                    ad_resp = scraper.get(url)
                else:
                    ad_resp = requests.get(url, headers=headers)
                    
                ad_soup = BeautifulSoup(ad_resp.content, 'html.parser')
                
                # 1. Check Timestamp
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

                # 3. Send Notification
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
    
    if new_ads_found == 0:
        # Debug: Print page title to see if blocked
        print(f"DEBUG: Page Title: {soup.title.string if soup.title else 'No Title'}")
        raise Exception("DEBUG: No guns found! Scraper might be blocked or keywords not matching.")

def send_telegram_message(message, config):
    token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    
    if not token or not chat_id:
        raise Exception("[-] Telegram secrets are MISSING! Check GitHub Settings.")

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        print(f"    Sending message to {chat_id}...")
        response = requests.post(url, data=data)
            
        if response.status_code != 200:
            raise Exception(f"[-] Telegram API Error: {response.text}")
            
        print("    [+] Message sent successfully!")
            
    except Exception as e:
        raise e

def main():
    print("Starting GunsArizona Bot...")
    config = load_config()
    
    # 1. Send Startup Message to verify Telegram is working
    print("[-] Attempting to send startup message...")
    try:
        send_telegram_message("⚠️ <b>DEBUG:</b> Bot started on GitHub!", config)
        print("[+] Startup message sent!")
    except Exception as e:
        print(f"[-] Startup message FAILED: {e}")
        raise e

    # 2. Run check
    check_for_guns()

if __name__ == "__main__":
    main()
