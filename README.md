# Scheduled scraper: Axon Fusus Surveillance Registries

This repository automatically scrapes and archives camera statistics, agency configurations, legal agreements, assets, and web pages across all subscriber portals hosted on the **Axon Fusus** platform (marketed as "Community Connect") nationwide.

It monitors:
*   **Platform Status & Routing**: Core Fusus platform version, service versions, and external domain routes (`fusus-system.json`).
*   **Agency Profiles & Legal Terms**: Organization configuration (`organization.json`) and full Memorandum of Understanding legal text (`mou.html`) for 328+ public safety agencies.
*   **Agency Badges & Insignia**: Official agency badge/logo binary images (`logo.{ext}`) cached locally per jurisdiction.
*   **Nationwide Surveillance Registries**: Camera metrics (registered, integrated, owned, shared, and subscribed counts) in append-only time series (`stats.jsonl`).
*   **Public Portal Web Pages**: HTML snapshots (`pages/`) across subscriber sites, plus legacy Seattle-specific page tracking.

For technical investigation details, reverse-engineering methodology, and design choices, see [ADR 001](doc/adr/001-api-discovery-and-caching.md).

---

## How It Works

This project uses [Git Scraping](https://simonwillison.net/2020/Oct/9/git-scraping/)—a technique popularized by Simon Willison—to pull updates on a schedule and commit any changes back to the repository.

1.  **GitHub Actions Workflow**: A scheduled workflow (`.github/workflows/scrape.yml`) runs daily.
2.  **Master Portals List**: `update-portals.py` queries `https://axoncommunityconnect.com/locations.json` and updates `fusus-portals.json` and `fusus-portals.geojson`.
3.  **Concurrent API & Data Collector**:
    *   Queries platform connectivity and system versioning: `https://api.fususone.com/api/public/connectivity-check/`
    *   The `scrape-fusus.py` script queries organization stats, metadata, MOUs, logos, and portal pages concurrently across all portals using a thread pool.
    *   Ephemeral AWS S3 presigned URL tokens (`AWSAccessKeyId`, `Signature`, `x-amz-security-token`, `Expires`) are sanitized before saving to ensure zero Git churn on identical data.
    *   Camera counts are appended to `data/{slug}/stats.jsonl` when counts change.
    *   Network timeouts or failures are logged to `data/{slug}/blocked.jsonl` without corrupting clean data files.
4.  **Seattle Browser Render**:
    *   Seattle's counters are loaded dynamically and animated client-side.
    *   `download.sh` uses `shot-scraper` (built on top of Playwright) to run a headless browser, wait 3 seconds for count animations to resolve, and dump fully-rendered HTML snapshots to root.
5.  **Semantic Commit Messages**:
    *   Before committing, `scripts/describe-diff.py` inspects staged changes and formats a commit message detailing platform updates, camera count changes, MOU revisions, metadata updates, and logo changes.

---

## Directory Structure

*   `fusus-system.json`: Fusus platform version, service health, and domain routing.
*   `fusus-portals.json`: Master database containing metadata (city, state, coordinates, url, registry link, organization code) for all Fusus portals.
*   `fusus-portals.geojson`: Geographic point features for map visualization.
*   `doc/adr/`: Architecture Decision Records documenting system design and investigations.
*   `data/{slug}/`:
    *   `stats.jsonl`: Time-stamped JSON records tracking camera statistics over time.
    *   `organization.json`: Agency profile, timezone, anonymous tip settings, and registration flags with canonical asset URLs.
    *   `mou.html`: Public Memorandum of Understanding legal text (when present).
    *   `logo.{ext}`: Downloaded agency badge/logo binary image.
    *   `pages/`: HTML snapshots of the agency's Community Connect web pages.
    *   `blocked.jsonl`: Error logs for rate limits or site failures.

---

## Scripts & Tools

### Update the Master Portals List
Downloads the latest list of portals from the database on `axoncommunityconnect.com` and formats them alphabetically by state and city:
```bash
./update-portals.py
```

### Scrape Camera Statistics
Triggers the concurrent stats collector for all listed portals:
```bash
./scrape-fusus.py
```

### Run the Full Scrape Pipeline
Runs the Fusus stats collector and fetches the Seattle HTML snapshots:
```bash
./scrape.sh
```

### Semantic Commit Summary
Reads the staged changes and prints the formatted commit message:
```bash
python3 scripts/describe-diff.py
```

---

## Running Scraper Locally

If you want to manually run the scraper on your machine, you must have Python, `uv`, and browser engines installed.

1.  **Install Browser Engine Dependencies**:
    ```bash
    uvx shot-scraper install
    ```

2.  **Execute the Scrape Pipeline**:
    ```bash
    ./scrape.sh
    ```
