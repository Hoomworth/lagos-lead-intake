import requests
import time
import random

# ---------------------------------------------------------
# HOOMWORTH CRM - LEAD SCRAPER ENGINE
# ---------------------------------------------------------
# This script runs completely separately from the Flask app.
# It finds data, packages it, and sends it to the CRM API.

# CHANGE THIS TO YOUR LIVE RENDER URL LATER (e.g., "https://hoomworth.onrender.com/api/add_scraped_lead")
API_ENDPOINT = "http://127.0.0.1:8080/api/add_scraped_lead"

def scrape_leads():
    print("🔍 SCRAPER: Initializing search for new property requests...")
    time.sleep(2) # Simulating the time it takes to scrape a website
    
    # For Phase 1 Testing, we are generating a highly realistic "Dummy Lead"
    # that mimics someone posting in a Facebook Group or Nairaland.
    scraped_lead = {
        "name": "Oluwaseun Babatunde",
        "phone": "08098765432",
        "budget": "₦4m - ₦6m",
        "location": "Lekki Phase 1 or Ikoyi",
        "property_type": "2 Bedroom Apartment",
        "timeline": "Immediate (Within 2 weeks)",
        "notes": "Original Post: 'Please I urgently need a serviced 2 bedroom in Lekki Phase 1 or Ikoyi. Budget is 5m max. Must have 24/7 power.'",
        "source": "Scraper"
    }
    
    return [scraped_lead]

def send_to_crm(leads):
    for lead in leads:
        print(f"🚀 SCRAPER: Found lead ({lead['name']}). Sending to CRM...")
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
    # 1. Gather leads from all platforms
    new_leads = run_all_scrapers()
    # 2. Push them to the database
    send_to_crm(new_leads)