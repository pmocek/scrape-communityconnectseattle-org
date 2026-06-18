# Scheduled scraper: communityconnectseattle.org

This repository automatically scrapes and tracks changes to [communityconnectseattle.org](https://communityconnectseattle.org), a public-safety camera integration initiative in Seattle.

Specifically, it monitors pages including:
- Home page: Displays statistics on registered/integrated cameras.
- Camera Registration
- Camera Integration
- Join
- Privacy Policy

---

## How It Works

This project uses **Git Scraping**—a technique popularized by Simon Willison—to pull updates on a schedule and commit any changes back to the repository.

1. **GitHub Actions Workflow**: A scheduled workflow (`.github/workflows/scrape.yml`) runs daily.
2. **Setup with `uv`**: The action sets up Python and the fast python package installer `uv`.
3. **Browser Automation (`shot-scraper`)**: Because the statistics on the site are loaded dynamically via APIs and rendered using an animated counter, a simple `curl` would miss the numbers. We use Simon Willison's `shot-scraper` (built on top of Playwright) to run a headless browser, wait for the scripts/animations to execute, and snapshot the final rendered HTML.
4. **Git Commits**: If any rendered HTML files have changed (e.g. camera counts incremented), they are committed back to the repository automatically.

---

## Important Scraper Configuration: Handling Counter Animations

If you examine the home page of Connect Seattle, it features a dynamic count of:
- **Registered Cameras** (e.g. `824`)
- **Integrated Cameras** (e.g. `715`)

These numbers are fetched asynchronously and animated (ticking up from `0` to the final count).

- **Standard `curl`**: Yields page source missing the numbers entirely.
- **`shot-scraper html` (without delay)**: Captures the page immediately on load, resulting in counts of `0`, blank strings, or partial animation ticks (e.g. `225` and `195`).
- **Wait Configuration**: In `download.sh`, we pass the `--wait 3000` parameter. This forces Playwright to wait 3 seconds before dumping the HTML snapshot, allowing the statistics API calls to resolve and the counter animations to finish.

---

## Running the Scraper Locally

If you want to manually run the scraper on your machine, you must have Python and `uv` installed.

1. **Install Browser Engine Dependencies**:
   ```bash
   uvx shot-scraper install
   ```

2. **Run the Scraping Script**:
   ```bash
   ./scrape.sh
   ```

This will run `download.sh` for each of the target URLs, rendering them and overwriting the local HTML files in this directory.
