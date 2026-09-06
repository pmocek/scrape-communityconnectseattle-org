#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
PROJECT_DIR = Path(__file__).parent.resolve()
PORTALS_FILE = PROJECT_DIR / "fusus-portals.json"
DATA_DIR = PROJECT_DIR / "data"
SYSTEM_FILE = PROJECT_DIR / "fusus-system.json"

MAX_WORKERS = 10
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FususClient/1.0"


def clean_system_data(data):
    """Normalize system status, stripping volatile timestamps to prevent git churn."""
    service_versions = {}
    for k, v in (data.get("serviceVersions") or {}).items():
        if isinstance(v, dict):
            # Exclude lastChecked timestamp which updates continuously
            service_versions[k] = {sk: sv for sk, sv in v.items() if sk != "lastChecked"}
        else:
            service_versions[k] = v

    return {
        "status": data.get("status"),
        "version": data.get("version"),
        "domains": data.get("domains"),
        "clientVersions": data.get("clientVersions"),
        "serviceVersions": service_versions,
    }


def scrape_system():
    """Fetch platform version and domain routing from connectivity-check."""
    url = "https://api.fususone.com/api/public/connectivity-check/"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw_data = json.loads(response.read().decode())
            clean_data = clean_system_data(raw_data)

            should_write = True
            if SYSTEM_FILE.exists():
                try:
                    with open(SYSTEM_FILE, "r") as f:
                        existing = json.load(f)
                    if existing == clean_data:
                        should_write = False
                except Exception:
                    should_write = True

            if should_write:
                with open(SYSTEM_FILE, "w") as f:
                    json.dump(clean_data, f, indent=2)
                print(f"System status updated (Fusus platform v{clean_data.get('version')}).")
            else:
                print(f"System status unchanged (Fusus platform v{clean_data.get('version')}).")
    except Exception as e:
        print(f"Warning: Could not fetch system connectivity status: {e}")


def sanitize_url(url):
    """Strip ephemeral AWS presigned query parameters to prevent git churn."""
    if not url:
        return url
    return url.split("?")[0]


def detect_image_ext(data, fallback=".png"):
    """Detect image file extension from magic bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    if b"<svg" in data[:100].lower():
        return ".svg"
    return fallback


def scrape_one(loc):
    org = loc.get("org")
    slug = loc.get("id")
    portal_url = loc.get("url")

    if not org:
        return {"slug": slug, "success": False, "error": "Missing org code"}

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    slug_dir = DATA_DIR / slug
    slug_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "slug": slug,
        "success": True,
        "stats_updated": False,
        "org_updated": False,
        "mou_updated": False,
        "logo_updated": False,
        "pages_updated": 0,
        "stats": {},
    }

    # 1. Scrape Camera Statistics
    stats_url = f"https://api.fususone.com/api/public/organizations/{org}/stats/"
    stats_req = urllib.request.Request(stats_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(stats_req, timeout=TIMEOUT) as response:
            stats = json.loads(response.read().decode())
            results["stats"] = stats

            stats_file = slug_dir / "stats.jsonl"
            should_write_stats = True
            if stats_file.exists():
                try:
                    with open(stats_file, "r") as f:
                        lines = f.readlines()
                        if lines:
                            last_line = ""
                            for line in reversed(lines):
                                if line.strip():
                                    last_line = line.strip()
                                    break
                            if last_line:
                                last_stats = json.loads(last_line)
                                keys_to_compare = [
                                    "totalRegisteredCameras",
                                    "totalIntegratedCameras",
                                    "totalOwnedCameras",
                                    "totalSharedCameras",
                                    "totalMaxCameras",
                                    "subscribedCameras",
                                ]
                                if all(last_stats.get(k) == stats.get(k) for k in keys_to_compare):
                                    should_write_stats = False
                except Exception:
                    should_write_stats = True

            if should_write_stats:
                stats_line = {"ts": ts, **stats}
                with open(stats_file, "a") as f:
                    f.write(json.dumps(stats_line) + "\n")
                results["stats_updated"] = True
    except urllib.error.HTTPError as e:
        error_line = {"ts": ts, "endpoint": "stats", "error": f"HTTPError {e.code}", "reason": e.reason}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": f"HTTP {e.code} on stats"}
    except urllib.error.URLError as e:
        error_line = {"ts": ts, "endpoint": "stats", "error": f"URLError {e.reason}"}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": f"URL {e.reason} on stats"}
    except Exception as e:
        error_line = {"ts": ts, "endpoint": "stats", "error": str(e)}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
        return {"slug": slug, "success": False, "error": str(e)}

    # 2. Scrape Organization Metadata, MOU, and Logo
    org_url = f"https://api.fususone.com/api/public/organizations/{org}/"
    org_req = urllib.request.Request(org_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(org_req, timeout=TIMEOUT) as response:
            raw_org = json.loads(response.read().decode())
            raw_logo_url = raw_org.get("logoUrl")

            # Sanitize ephemeral S3 URLs
            clean_org = dict(raw_org)
            for url_field in ["logoUrl", "loginVideoUrl", "backgroundUrl", "favicoUrl", "registryRedirectUrl"]:
                if url_field in clean_org:
                    clean_org[url_field] = sanitize_url(clean_org[url_field])

            org_file = slug_dir / "organization.json"
            should_write_org = True
            if org_file.exists():
                try:
                    with open(org_file, "r") as f:
                        existing_org = json.load(f)
                    if existing_org == clean_org:
                        should_write_org = False
                except Exception:
                    should_write_org = True

            if should_write_org:
                with open(org_file, "w") as f:
                    json.dump(clean_org, f, indent=2)
                results["org_updated"] = True

            # Extract MOU template if present
            mou_template = raw_org.get("mou", {}).get("mouTemplate")
            if mou_template:
                mou_file = slug_dir / "mou.html"
                should_write_mou = True
                if mou_file.exists():
                    try:
                        with open(mou_file, "r", encoding="utf-8") as f:
                            if f.read() == mou_template:
                                should_write_mou = False
                    except Exception:
                        should_write_mou = True

                if should_write_mou:
                    with open(mou_file, "w", encoding="utf-8") as f:
                        f.write(mou_template)
                    results["mou_updated"] = True

            # Download Logo binary if present
            if raw_logo_url:
                try:
                    logo_req = urllib.request.Request(raw_logo_url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(logo_req, timeout=TIMEOUT) as logo_resp:
                        logo_bytes = logo_resp.read()
                        ext = detect_image_ext(logo_bytes)
                        logo_file = slug_dir / f"logo{ext}"

                        should_write_logo = True
                        if logo_file.exists():
                            try:
                                with open(logo_file, "rb") as f:
                                    if f.read() == logo_bytes:
                                        should_write_logo = False
                            except Exception:
                                should_write_logo = True

                        if should_write_logo:
                            with open(logo_file, "wb") as f:
                                f.write(logo_bytes)
                            results["logo_updated"] = True
                except Exception:
                    # Non-fatal if logo fails to download
                    pass

    except urllib.error.HTTPError as e:
        error_line = {"ts": ts, "endpoint": "organization", "error": f"HTTPError {e.code}", "reason": e.reason}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")
    except Exception as e:
        error_line = {"ts": ts, "endpoint": "organization", "error": str(e)}
        with open(slug_dir / "blocked.jsonl", "a") as f:
            f.write(json.dumps(error_line) + "\n")

    # 3. Scrape Portal Web Pages
    if portal_url:
        pages_dir = slug_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        pages_to_fetch = [
            ("", "index.html"),
            ("camera-registration/", "camera-registration.html"),
            ("camera-integration/", "camera-integration.html"),
            ("join/", "join.html"),
            ("privacy-policy/", "privacy-policy.html"),
        ]

        for subpath, filename in pages_to_fetch:
            page_url = urllib.parse.urljoin(portal_url.rstrip("/") + "/", subpath)
            try:
                page_req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(page_req, timeout=TIMEOUT) as page_resp:
                    if page_resp.status == 200:
                        page_html = page_resp.read().decode("utf-8", errors="replace")
                        page_file = pages_dir / filename
                        should_write_page = True
                        if page_file.exists():
                            try:
                                with open(page_file, "r", encoding="utf-8") as f:
                                    if f.read() == page_html:
                                        should_write_page = False
                            except Exception:
                                should_write_page = True

                        if should_write_page:
                            with open(page_file, "w", encoding="utf-8") as f:
                                f.write(page_html)
                            results["pages_updated"] += 1
            except Exception:
                # Omit subpages that return 404 or fail without polluting error logs
                pass

    return results


def main():
    if not PORTALS_FILE.exists():
        print(f"ERROR: {PORTALS_FILE} not found. Run update-portals.py first.")
        sys.exit(1)

    with open(PORTALS_FILE) as f:
        portals = json.load(f)

    # 1. Fetch system platform status
    scrape_system()

    # 2. Scrape portals
    print(f"Loaded {len(portals)} portals. Scraping all available data with {MAX_WORKERS} workers...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_one, loc): loc for loc in portals}

        for future in as_completed(futures):
            loc = futures[future]
            try:
                res = future.result()
                results.append(res)
                if res["success"]:
                    reg = res["stats"].get("totalRegisteredCameras", 0)
                    integ = res["stats"].get("totalIntegratedCameras", 0)
                    changes = []
                    if res.get("stats_updated"):
                        changes.append("stats")
                    if res.get("org_updated"):
                        changes.append("org")
                    if res.get("mou_updated"):
                        changes.append("mou")
                    if res.get("logo_updated"):
                        changes.append("logo")
                    if res.get("pages_updated", 0) > 0:
                        changes.append(f"{res['pages_updated']} pages")

                    status_str = ", ".join(changes) if changes else "no change"
                    print(f"  {res['slug']}: OK ({status_str} - Registered: {reg}, Integrated: {integ})")
                else:
                    print(f"  {res['slug']}: FAILED - {res['error']}")
            except Exception as e:
                print(f"  {loc.get('id')}: Future raised exception: {e}")

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    print(f"\nDone. Successfully scraped {success_count}/{len(portals)} Fusus portals in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()

