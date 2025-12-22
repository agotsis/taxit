import requests
import json
import time
import os
import yaml
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pathlib import Path
import threading

load_dotenv()

API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

default_place_ids = [
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

# Thread-safe counter and lock
processed_count = 0
error_count = 0
count_lock = threading.Lock()

def process_place_id(place_id, output_file):
    """Process a single place ID and save the result."""
    global processed_count, error_count
    
    try:
        # STEP 1: Try to get the data we actually want
        data = fetch_details(place_id, basic_fields_str)
        status = data.get("status")
        
        # Inject ID for tracking
        data['requested_id'] = place_id
        data['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save all responses to JSONL (including errors)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        
        # Update counters thread-safely
        with count_lock:
            if status == "OK":
                result = data.get("result", {})
                returned_id = result.get("place_id")
                
                # Check if Google gave us a new ID (Redirect)
                if returned_id and returned_id != place_id:
                    print(f"⚠️  REDIRECT: {place_id} -> {returned_id}")
                else:
                    print(f"✅ OK: {place_id}")
                processed_count += 1
                
            elif status == "NOT_FOUND":
                # --- FAILURE CASE: Try the "Free Refresh" ---
                print(f"❓ NOT_FOUND: {place_id}. Attempting free refresh...")
                
                # We call the API again, asking ONLY for the ID.
                refresh_data = fetch_details(place_id, refresh_fields_str)
                refresh_status = refresh_data.get("status")
                
                if refresh_status == "OK":
                    new_id = refresh_data["result"]["place_id"]
                    print(f"♻️  RESURRECTED: {place_id} -> {new_id}")
                    processed_count += 1
                else:
                    print(f"❌ DEAD: {place_id} is permanently gone.")
                    error_count += 1
                    
            else:
                # Other errors (OVER_QUERY_LIMIT, REQUEST_DENIED, etc.)
                print(f"⚠️  ERROR: {place_id} returned {status}")
                error_count += 1
        
        return True
        
    except Exception as e:
        print(f"❌ EXCEPTION: {place_id} - {e}")
        with count_lock:
            error_count += 1
        return False

def load_existing_ids(output_file="places_data_dump.jsonl"):
    """Load place IDs that are already in the data dump file."""
    existing_ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
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

def extract_place_ids_from_yaml(yaml_path):
    """Extract all unique placeIds from the YAML file by parsing it properly."""
    place_ids = set()
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
            
            def find_place_ids(obj):
                """Recursively find all placeId keys in the YAML structure."""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == 'placeId' and isinstance(value, str):
                            place_ids.add(value)
                        else:
                            find_place_ids(value)
                elif isinstance(obj, list):
                    for item in obj:
                        find_place_ids(item)
            
            find_place_ids(data)
            
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            return set()
    
    return place_ids

def main():
    parser = argparse.ArgumentParser(description='Fetch Google Places data for place IDs')
    parser.add_argument('--yaml', help='YAML file to extract place IDs from')
    parser.add_argument('--output', default="places_data_dump.jsonl", help='Output JSONL file')
    parser.add_argument('--workers', type=int, default=10, help='Number of concurrent workers')
    args = parser.parse_args()
    
    # Set output file from args
    output_file = args.output
    
    # Reset global counters
    global processed_count, error_count
    processed_count = 0
    error_count = 0
    
    # Determine place IDs source
    if args.yaml:
        yaml_path = Path(args.yaml)
        if not yaml_path.exists():
            print(f"Error: YAML file {args.yaml} not found")
            return 1
        print(f"Extracting placeIds from {args.yaml}...")
        place_ids = extract_place_ids_from_yaml(yaml_path)
        print(f"Found {len(place_ids)} unique placeIds")
    else:
        place_ids = set(default_place_ids)
        print(f"Using default test place IDs ({len(place_ids)} IDs)")
    
    existing_ids = load_existing_ids(output_file)
    print(f"Found {len(existing_ids)} IDs already in data dump")
    
    # Filter out IDs we already have
    new_place_ids = [pid for pid in place_ids if pid not in existing_ids]
    print(f"{len(new_place_ids)} new IDs to fetch")
    
    if not new_place_ids:
        print("All placeIds already processed!")
        return 0
    
    print(f"Processing {len(new_place_ids)} new IDs with {args.workers} workers...")
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_place_id = {
            executor.submit(process_place_id, place_id, output_file): place_id 
            for place_id in sorted(new_place_ids)
        }
        
        # Wait for all to complete
        for future in as_completed(future_to_place_id):
            place_id = future_to_place_id[future]
            try:
                future.result()
            except Exception as e:
                print(f"❌ FUTURE EXCEPTION: {place_id} - {e}")
                with count_lock:
                    error_count += 1
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {processed_count}")
    print(f"Errors: {error_count}")
    print(f"Data saved to: {output_file}")
    return 0

if __name__ == "__main__":
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not found in environment variables")
        exit(1)
    exit(main())