# Scheduled scraper: Fusus Community Connect

This repository automatically scrapes and tracks camera statistics across all participating communities hosted on the **Axon Fusus** platform nationwide, alongside HTML snapshot differences for [communityconnectseattle.org](https://communityconnectseattle.org).

It monitors:
*   **Seattle-specific Pages**: Full HTML snapshots (home page, camera registration, integration, join, and privacy policy) to track layout or policy modifications.
*   **Nationwide Community Connect Portals**: Camera metrics (registered, integrated, owned, shared, and subscribed counts) for **300+ participating agencies** across dozens of states.

---

## How It Works

This project uses **Git Scraping**—popularized by Simon Willison—to pull updates on a schedule and commit any changes back to the repository.

1.  **GitHub Actions Workflow**: A scheduled workflow (`.github/workflows/scrape.yml`) runs daily.
2.  **Master Community List**: The file `fusus-communities.json` serves as the list of monitored agencies.
3.  **Concurrent API Stats Scraper**:
    *   Fusus hosts a public JSON endpoint for organization stats: `https://api.fususone.com/api/public/organizations/{org}/stats/`
    *   The `scrape-fusus.py` script queries this API concurrently for all 300+ agencies using a thread pool, finishing in under 5 seconds.
    *   Metrics are appended as time-staged lines to `data/{slug}/stats.jsonl`.
    *   Network timeouts or failures are logged to `data/{slug}/blocked.jsonl` without corrupting the clean stats log.
4.  **Seattle Browser Render**:
    *   Seattle's counters are loaded dynamically and animated client-side.
    *   `download.sh` uses `shot-scraper` (built on top of Playwright) to run a headless browser, wait 3 seconds for count animations to resolve, and dump the fully-rendered HTML snapshot.
5.  **Semantic Commit Messages**:
    *   Before committing, `scripts/describe-diff.py` compares the staged changes to `stats.jsonl` files and formats a commit message detailing how many portals updated and summarizing camera count gains/losses (e.g., `data: update 4 Fusus portals (renton-wa: integrated ▲3)`).

---

## Directory Structure

*   `fusus-communities.json`: Master database containing metadata (city, state, coordinates, url, registry link, organization code) for all Fusus communities.
*   `data/{slug}/stats.jsonl`: Time-stamped JSON records tracking camera statistics over time.
    ```json
    {"ts": "2026-06-30T22:13:36Z", "totalRegisteredCameras": 844, "totalIntegratedCameras": 709, "totalOwnedCameras": 692, "totalSharedCameras": 0, "totalMaxCameras": 5000, "subscribedCameras": 689}
    ```
*   `data/{slug}/blocked.jsonl`: Error logs for rate limits or site failures.

---

## Scripts & Tools

### Update the Master Community List
Downloads the latest list of communities from the official map database on `axoncommunityconnect.com` and formats them alphabetically by state and city:
```bash
./update-communities.py
```

### Scrape Camera Statistics
Triggers the concurrent stats collector for all listed communities:
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
