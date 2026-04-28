import requests
import time
import random
import datetime
import re
import urllib.parse

# Selenium for Web Browser Automation
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ---------------------------------------------------------
# HOOMWORTH CRM - LEAD SCRAPER ENGINE
# ---------------------------------------------------------
# This script runs completely separately from the Flask app.
# It finds data, packages it, and sends it to the CRM API.

# Your live Render URL
# API_ENDPOINT = "https://lagos-lead-intake.onrender.com/api/add_scraped_lead"
# LOCAL TESTING: 
API_ENDPOINT = "http://127.0.0.1:8080/api/add_scraped_lead"

def scrape_x_twitter():
    print("🔍 SCRAPER: Waking up our virtual Chrome browser...")
    
    # Setup Chrome (Visible, not headless, to avoid bot detection and allow manual login)
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except Exception as e:
        print(f"❌ Failed to launch Chrome: {e}")
        return []
        
    leads = []
    
    try:
        print("🌐 Opening X (Twitter) Login Page...")
        driver.get("https://x.com/login")
        
        print("\n" + "="*50)
        print("🚨 ACTION REQUIRED 🚨")
        print("1. A new Chrome window just opened on your screen.")
        print("2. Please log in to a dummy/secondary X account in that window.")
        print("3. Once you are fully logged in and see the home timeline, come back here.")
        print("="*50 + "\n")
        
        input("👉 Press ENTER in this terminal when you are fully logged in... ")
        
        print("\n📡 Searching for live buyers in Lagos...")
        
        # The Ultimate Real Estate Search Query for Nigeria
        search_query = '("need a house" OR "looking for apartment" OR "looking for a house" OR "need an agent" OR "want to rent" OR "want to buy") (Lagos OR Lekki OR Yaba OR Ikeja OR Mainland)'
        encoded_query = urllib.parse.quote(search_query)
        
        # f=live means "Latest" tweets
        search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"
        driver.get(search_url)
        
        print("⏳ Waiting 10 seconds for tweets to load...")
        time.sleep(10)
        
        # Scroll down twice to load more results
        for i in range(2):
            print(f"   ⬇️ Scrolling page {i+1}...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(4)
            
        # Find all tweets on the page
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweetText"]')
        print(f"📝 Found {len(tweet_elements)} recent tweets matching our keywords. Extracting...")
        
        for tweet in tweet_elements:
            text = tweet.text.strip()
            # Skip extremely short/empty posts
            if len(text) > 20:
                unique_url = f"{search_url}&unique={abs(hash(text))}"
                leads.append({
                    "raw_text": text,
                    "source": "X (Twitter)",
                    "url": unique_url
                })
                
    except Exception as e:
        print(f"❌ ERROR DURING SCRAPING: {e}")
    finally:
        print("🛑 Closing browser...")
        driver.quit()
        
    return leads

def send_to_crm(leads):
    if not leads:
        print("🛑 SCRAPER: No leads gathered in this session.")
        return
        
    for lead in leads:
        print(f"🚀 SCRAPER: Sending raw post to CRM for AI Parsing...")
        try:
            response = requests.post(API_ENDPOINT, json=lead)
            if response.status_code == 201:
                data = response.json()
                print(f"✅ SUCCESS: Lead securely delivered and assigned to {data['assigned_to']}!")
            elif response.status_code == 200 and response.json().get("status") == "skipped":
                print(f"⚠️ SKIPPED: URL already exists in CRM.")
            else:
                print(f"❌ ERROR: Failed to deliver lead. Server responded: {response.text}")
        except requests.exceptions.ConnectionError:
            print("❌ ERROR: Could not connect to CRM. Is the Flask server running?")

if __name__ == "__main__":
    print("========================================")
    print("STARTING MULTI-SITE LEAD ENGINE")
    print("========================================")
    
    all_leads = []
    all_leads.extend(scrape_x_twitter())
    
    send_to_crm(all_leads)
    print("🏁 SCRAPER: All tasks completed successfully! You can run me again later.")