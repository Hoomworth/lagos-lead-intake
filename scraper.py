import requests
import time
import random
import cloudscraper
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# HOOMWORTH CRM - LEAD SCRAPER ENGINE
# ---------------------------------------------------------
# This script runs completely separately from the Flask app.
# It finds data, packages it, and sends it to the CRM API.

# Your live Render URL
API_ENDPOINT = "https://lagos-lead-intake.onrender.com/api/add_scraped_lead"

def scrape_leads():
    print("🔍 SCRAPER: Connecting to Nairaland Property Section...")
    
    url = "https://www.nairaland.com/properties"
    
    scraped_leads = []
    
    try:
        # Create a special scraper to bypass Cloudflare security
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Grab all link tags on the page
        topics = soup.find_all('a')
        
        # Filter out short links and external links
        valid_topics = [t for t in topics if t.text and len(t.text.strip()) > 15 and t.get('href') and not t.get('href').startswith('http')]
        print(f"📡 SCRAPER: Found {len(valid_topics)} potential threads. Filtering for buyer requests...")
        
        # 70+ Perfect High-Intent Real Estate Keywords
        keywords = [
            'need a', 'needed', 'looking for', 'buyer', 'urgent', 'rent', 'lease', 'buy',
            'searching for', 'seeking', 'budget is', 'client needs', 'direct brief', 'urgently',
            'require', 'accommodation', 'apartment needed', 'house wanted', 'land wanted',
            'office space', 'shop needed', 'warehouse needed', 'tenant', 'purchaser',
            'looking to buy', 'looking to rent', 'want to buy', 'want to rent', 'in need of',
            'ready to pay', 'ready to buy', 'ready buyer', 'urgent request', 'serious buyer',
            'serious client', 'need a 2 bed', 'need a 3 bed', 'mini flat', 'self contain',
            'duplex needed', 'half plot', 'full plot', 'acres needed', 'property wanted',
            'house hunting', 'apartment hunting', 'any available', 'who has', 'where can i get',
            'looking for a', 'search of', 'to let', 'for lease', 'shortlet needed', 'short let needed',
            'expatriate looking', 'company looking', 'staff looking', 'family looking',
            'couple looking', 'bachelor looking', 'bq needed', 'boys quarter needed'
        ]
        
        # Negative Keywords to filter out ads and spam
        negative_keywords = [
            'call', 'whatsapp', 'check out', 'look no further', 'our services',
            'we sell', 'custom', 'working drawings', 'stamp', 'for any property you need',
            'contact us', 'hire us', 'available for sale', 'to let'
        ]
        
        for topic in valid_topics[:100]: # Scan the top 100 links
            title_text = topic.text.strip()
            
            if any(kw in title_text.lower() for kw in keywords) and not any(n_kw in title_text.lower() for n_kw in negative_keywords):
                thread_url = "https://www.nairaland.com/" + topic.get('href').lstrip('/')
                print(f"📝 Found Match: {title_text}")
                print(f"   🔗 Deep Scraping Thread: {thread_url}")
                
                try:
                    # DEEP SCRAPING: Visit the actual thread to get the full post body
                    thread_response = scraper.get(thread_url)
                    thread_soup = BeautifulSoup(thread_response.text, "html.parser")
                    first_post = thread_soup.find('div', class_='narrow')
                    full_text = first_post.text.strip() if first_post else title_text
                    
                    scraped_leads.append({
                        "raw_text": full_text,
                        "source": "Nairaland Scraper",
                        "url": thread_url
                    })
                    time.sleep(1) # Be polite to the server
                except Exception as e:
                    print(f"   ❌ Failed to read thread: {e}")
                
        return scraped_leads
        
    except Exception as e:
        print(f"❌ ERROR SCRAPING: {e}")
        return []

def send_to_crm(leads):
    for lead in leads:
        print(f"🚀 SCRAPER: Sending raw post to CRM for AI Parsing...")
        try:
            response = requests.post(API_ENDPOINT, json=lead)
            if response.status_code == 201:
                data = response.json()
                print(f"✅ SUCCESS: Lead securely delivered and assigned to {data['assigned_to']}!")
            else:
                print(f"❌ ERROR: Failed to deliver lead. Server responded: {response.text}")
        except requests.exceptions.ConnectionError:
            print("❌ ERROR: Could not connect to CRM. Is the Flask server running?")

if __name__ == "__main__":
    # 1. Find the leads
    new_leads = scrape_leads()
    # 2. Push them to the database
    send_to_crm(new_leads)