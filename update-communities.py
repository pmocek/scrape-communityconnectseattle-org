#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
from pathlib import Path

URL = "https://axoncommunityconnect.com/locations.json"
OUTPUT_FILE = Path(__file__).parent / "fusus-communities.json"

def main():
    print(f"Fetching Fusus communities list from {URL}...")
    
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"Error fetching communities list: {e}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        exit(1)
        
    print(f"Found {len(data)} communities. Formatting and sorting...")
    
    # Sort by state, city, and title
    data.sort(key=lambda x: (
        x.get("location", {}).get("state", "").upper(),
        x.get("location", {}).get("city", "").lower(),
        x.get("title", "").lower()
    ))
    
    # Write clean JSON
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully updated communities list. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
