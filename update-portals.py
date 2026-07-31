#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
from pathlib import Path

URL = "https://axoncommunityconnect.com/locations.json"
OUTPUT_FILE = Path(__file__).parent / "fusus-portals.json"

def main():
    print(f"Fetching Fusus portals list from {URL}...")
    
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"Error fetching portals list: {e}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        exit(1)
        
    print(f"Found {len(data)} portals. Formatting and sorting...")
    
    # Sort by state, city, and title
    data.sort(key=lambda x: (
        x.get("location", {}).get("state", "").upper(),
        x.get("location", {}).get("city", "").lower(),
        x.get("title", "").lower()
    ))
    
    # Write clean JSON
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
        
    # Write GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    for item in data:
        coords = item.get("location", {}).get("coords", {})
        lat = coords.get("lat")
        lng = coords.get("lng")
        if lat is not None and lng is not None:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "city": item.get("location", {}).get("city"),
                    "state": item.get("location", {}).get("state"),
                    "registry": item.get("registry"),
                    "org": item.get("org"),
                    "image": item.get("image")
                }
            }
            geojson["features"].append(feature)
            
    GEOJSON_OUTPUT = Path(__file__).parent / "fusus-portals.geojson"
    with open(GEOJSON_OUTPUT, "w") as f:
        json.dump(geojson, f, indent=2)
        
    print(f"Successfully updated portals list. Saved to {OUTPUT_FILE} and {GEOJSON_OUTPUT}")

if __name__ == "__main__":
    main()


