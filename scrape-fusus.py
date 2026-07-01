#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
PROJECT_DIR = Path(__file__).parent.resolve()
COMMUNITIES_FILE = PROJECT_DIR / "fusus-communities.json"
DATA_DIR = PROJECT_DIR / "data"

MAX_WORKERS = 10
TIMEOUT = 10

def scrape_one(loc):
    org = loc.get("org")
    slug = loc.get("id")
    title = loc.get("title", slug)
    
    if not org:
        return {"slug": slug, "success": False, "error": "Missing org code"}
        
    url = f"https://api.fususone.com/api/public/organizations/{org}/stats/"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FususScraper/1.0"}
    )
    
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    slug_dir = DATA_DIR / slug
    
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.status
            body = response.read().decode()
            stats = json.loads(body)
            
            # Ensure directories exist
            slug_dir.mkdir(parents=True, exist_ok=True)
            
            # Write stats.jsonl (append)
            stats_line = {"ts": ts, **stats}
            with open(slug_dir / "stats.jsonl", "a") as f:
                f.write(json.dumps(stats_line) + "\n")
                
            return {"slug": slug, "success": True, "stats": stats}
            
    except urllib.error.HTTPError as e:
        slug_dir.mkdir(parents=True, exist_ok=True)
        # Log HTTP errors (like 429 rate limit or 500 server error)
        error_line = {"ts": ts, "error": f"HTTPError {e.code}", "reason": e.reason}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": f"HTTP {e.code}"}
        
    except urllib.error.URLError as e:
        slug_dir.mkdir(parents=True, exist_ok=True)
        error_line = {"ts": ts, "error": f"URLError {e.reason}"}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": f"URL {e.reason}"}
        
    except Exception as e:
        slug_dir.mkdir(parents=True, exist_ok=True)
        error_line = {"ts": ts, "error": str(e)}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": str(e)}

def main():
    if not COMMUNITIES_FILE.exists():
        print(f"ERROR: {COMMUNITIES_FILE} not found. Run update-communities.py first.")
        sys.exit(1)
        
    with open(COMMUNITIES_FILE) as f:
        communities = json.load(f)
        
    print(f"Loaded {len(communities)} communities. Scraping stats with {MAX_WORKERS} workers...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_one, loc): loc for loc in communities}
        
        for future in as_completed(futures):
            loc = futures[future]
            try:
                res = future.result()
                results.append(res)
                if res["success"]:
                    reg = res["stats"].get("totalRegisteredCameras", 0)
                    integ = res["stats"].get("totalIntegratedCameras", 0)
                    print(f"  {res['slug']}: OK (Registered: {reg}, Integrated: {integ})")
                else:
                    print(f"  {res['slug']}: FAILED - {res['error']}")
            except Exception as e:
                print(f"  {loc.get('id')}: Future raised exception: {e}")
                
    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    print(f"\nDone. Successfully scraped {success_count}/{len(communities)} Fusus communities in {elapsed:.1f}s.")

if __name__ == "__main__":
    main()
