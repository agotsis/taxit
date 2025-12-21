import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
OUTPUT_DATA_FILE = "places_data_dump.jsonl"

# Test IDs
place_ids = [
    "ChIJVTPokywQkFQRmtVEaUZlJRA", # Valid (Space Needle)
    "ChIJp5d_W2H9mokRSlVpT336qGk", # The ID from your error (Empire State - likely valid but let's test)
    "ChIJ_FAKE_DEAD_ID_12345",     # Simulating a dead ID
]

basic_fields = [
    "address_component", "adr_address", "business_status", "formatted_address",
    "geometry", "icon", "name", "place_id", "type", "url", "vicinity"
]
basic_fields_str = ",".join(basic_fields)
refresh_fields_str = "place_id"

def load_existing_ids():
    """Load place IDs that are already in the data dump file."""
    existing_ids = set()
    if os.path.exists(OUTPUT_DATA_FILE):
        with open(OUTPUT_DATA_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        # Check both the requested_id and the result's place_id
                        requested_id = data.get('requested_id')
                        result_id = data.get('result', {}).get('place_id')
                        if requested_id:
                            existing_ids.add(requested_id)
                        if result_id:
                            existing_ids.add(result_id)
                    except json.JSONDecodeError:
                        print("JSON was not valid! Skipping.")
                        continue
    return existing_ids

def fetch_details(place_id, fields):
    """
    Generic fetcher that can switch between full data and ID-only.
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id, 
        "fields": fields, 
        "key": API_KEY
    }
    return requests.get(url, params=params).json()

existing_ids = load_existing_ids()
print(f"Found {len(existing_ids)} IDs already in data dump")

# Filter out IDs we already have
new_place_ids = [pid for pid in place_ids if pid not in existing_ids]
print(f"{len(new_place_ids)} new IDs to fetch")

print(f"Processing {len(new_place_ids)} new IDs...")

for old_id in new_place_ids:
    # STEP 1: Try to get the data we actually want
    data = fetch_details(old_id, basic_fields_str)
    status = data.get("status")
    
    # Inject ID for tracking
    data['requested_id'] = old_id

    # Save all responses to JSONL (including errors)
    with open(OUTPUT_DATA_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data) + "\n")

    if status == "OK":
        # --- SUCCESS CASE ---
        result = data.get("result", {})
        returned_id = result.get("place_id")

        # Check if Google gave us a new ID (Redirect)
        if returned_id and returned_id != old_id:
            print(f"⚠️  REDIRECT: {old_id} -> {returned_id}")
        else:
            print(f"✅ OK: {old_id}")

    elif status == "NOT_FOUND":
        # --- FAILURE CASE: Try the "Free Refresh" ---
        print(f"❓ NOT_FOUND: {old_id}. Attempting free refresh...")
        
        # We call the API again, asking ONLY for the ID.
        # This follows the docs: "specifying only the place ID field"
        refresh_data = fetch_details(old_id, refresh_fields_str)
        refresh_status = refresh_data.get("status")

        if refresh_status == "OK":
            new_id = refresh_data["result"]["place_id"]
            print(f"♻️  RESURRECTED: {old_id} -> {new_id}")
        else:
            print(f"❌ DEAD: {old_id} is permanently gone.")

    else:
        # Other errors (OVER_QUERY_LIMIT, REQUEST_DENIED, etc.)
        print(f"⚠️  ERROR: {old_id} returned {status}")
    
    time.sleep(0.1)

print(f"\nDone. All responses saved to '{OUTPUT_DATA_FILE}'.")