# ADR 001: Public API Discovery and Nationwide Data Caching

**Date:** 2026-09-05  
**Status:** Accepted  

## Context

This project originally monitored [communityconnectseattle.org](https://communityconnectseattle.org) by taking browser-rendered HTML snapshots of Seattle's public safety camera portal and appending camera counts to a time-series log. Over time, the scope expanded to scrape camera count statistics across all 328+ municipal portals hosted on the Axon Fusus platform (marketed as "Community Connect") nationwide using the public endpoint `https://api.fususone.com/api/public/organizations/{org}/stats/`.

However, the repository was omitting significant public data exposed by Axon's infrastructure, including agency metadata, configuration settings, legal Memorandums of Understanding (MOU), citizen camera registration disclosures, agency badges/logos, and platform software versioning. Furthermore, rendered page snapshots were restricted exclusively to Seattle despite hundreds of communities running live portals.

Before expanding the scraper, we conducted a technical investigation to map all publicly accessible data endpoints across Axon's servers.

### Investigation Methodology

1. **Frontend Bundle Reverse-Engineering:**
   * Analyzed the compiled Angular application bundles and chunk manifests served by the public camera registry portal (`https://seattlepd.fususregistry.com/`): `runtime.5b530a86dc72a180.js`, `main.8a8b170d1126769b.js`, and `vendor.39bd774b7121f00d.js`.
   * Scanned all **361 compiled lazy-loaded JavaScript chunk modules** to extract every HTTP client invocation (`this._httpClient.*`) and route matching `/api/`.
   * **Findings:**
     * **Public GET Endpoints:** The *only* unauthenticated GET endpoints implemented in the entire frontend platform are:
       1. `GET /api/public/connectivity-check/` (Platform status, system versions, service domain routing)
       2. `GET /api/public/organizations/{org}/` (Organization profile, legal terms, settings, asset URLs)
       3. `GET /api/public/organizations/{org}/stats/` (Live camera metrics)
     * **Public POST Endpoints:** Two unauthenticated POST endpoints exist exclusively for public camera registration submissions:
       1. `POST /api/public/registry/quick/` (Citizen camera registration form submission)
       2. `POST /api/public/registry/confirm/` (Registrant email verification)
     * **Protected Endpoints:** All remaining backend APIs (`/api/cameras/`, `/api/lpr/`, `/api/alarms/`, `/api/vaults/`, `/api/audit/`, etc.) require police/operator authentication via JWT tokens (`/api/auth/jwt/obtain/`) and return HTTP 401/403.

2. **API Discovery & Specification Probing:**
   * Probed standard REST discovery and OpenAPI/Swagger documentation paths on `https://api.fususone.com` (`/openapi.json`, `/api/openapi.json`, `/api/swagger.json`, `/api/docs`, `/docs`, `/api/v1/`, etc.).
   * All returned HTTP 404 (Not Found). OpenAPI documentation and schema reflection are disabled on public routes.
   * The platform's functional status endpoint is `/api/public/connectivity-check/`.

3. **Vendor & Developer Documentation Review:**
   * Reviewed Axon's public developer resources (`developers.axon.com`). Public documentation focuses on Evidence.com and partner hardware integrations (e.g., Verkada, Skydio). Fusus Real-Time Crime Center (RTCC) API specifications are restricted under customer/partner Non-Disclosure Agreements (NDAs).
   * Procurement filings confirm that Fusus restricts external queries to public registration and community counter endpoints.
   * The master directory for all nationwide subscriber portals is published at `https://axoncommunityconnect.com/locations.json`.

---

## Decision

We expand the automated scraper from a stats-only tool to a comprehensive nationwide archive of all available public Axon/Fusus data:

1. **System & Platform Status (`fusus-system.json` at root):**
   * Query `https://api.fususone.com/api/public/connectivity-check/`.
   * Record Fusus platform version (e.g., `2026.31.3`), internal service versions (`ruleengine`), and service domain mappings.
   * Normalize out the millisecond `serverTime` field to prevent daily false Git diffs.
   * Store at the repository root alongside `fusus-portals.json` to keep `data/` reserved strictly for `{slug}` folders.

2. **Per-Organization Metadata (`data/{slug}/organization.json`):**
   * Query `https://api.fususone.com/api/public/organizations/{org}/` for each portal.
   * **Sanitization of Presigned S3 URLs:** Asset fields (`logoUrl`, `loginVideoUrl`, `backgroundUrl`) point to Amazon S3 using presigned URLs containing ephemeral credentials (`AWSAccessKeyId`, `Signature`, `x-amz-security-token`, `Expires`) that rotate on every HTTP request. To prevent infinite Git churn, strip query parameters to persist stable canonical URLs.
   * Save formatted JSON only when sanitized contents change.

3. **Memorandum of Understanding (`data/{slug}/mou.html`):**
   * Extract the raw HTML template of the legal agreement (`mou.mouTemplate`) into a dedicated `data/{slug}/mou.html` file whenever present.
   * This provides immediate human readability and enables precise Git line-diff tracking when municipalities revise video sharing terms, liability clauses, or public records disclosures.

4. **Agency Badges / Logos (`data/{slug}/logo.{ext}`):**
   * Download binary agency badge/logo assets locally to `data/{slug}/logo.{ext}`.
   * This ensures downstream consumers and generated analysis sites can display official agency insignia without making external requests to Axon's S3 storage.

5. **Camera Statistics (`data/{slug}/stats.jsonl`):**
   * Continue append-only tracking of camera metrics (`totalRegisteredCameras`, `totalIntegratedCameras`, `totalOwnedCameras`, `totalSharedCameras`, `totalMaxCameras`, `subscribedCameras`) when values change.

6. **Nationwide Web Page Snapshots (`data/{slug}/pages/`):**
   * Expand web page archiving from Seattle to all 328+ jurisdictions.
   * Scrape each portal's base URL and primary subpages (`/camera-registration/`, `/camera-integration/`, `/join/`, `/privacy-policy/`), saving to `data/{slug}/pages/{page}.html`.
   * For Seattle, continue mirroring to root (`communityconnectseattle.org*.html`) to maintain backward compatibility.

7. **Semantic Commit Summaries (`scripts/describe-diff.py`):**
   * Update the commit message generator to parse and describe changes to platform versions, organization configurations, MOU revisions, and logo updates.

---

## Consequences

### Positive
* Complete historical capture of all public Axon/Fusus data across all jurisdictions.
* Policy changes and legal terms (MOU) become easily auditable via standard Git diffs.
* Binary agency assets are preserved locally without runtime dependencies on external S3 buckets.
* Presigned S3 token stripping ensures zero Git churn when data has not meaningfully changed.
* Backward compatibility for Seattle-specific files and tools is fully preserved.

### Negative / Trade-offs
* Increased repository size over time due to binary logo assets and HTML snapshots.
* Scraping runtime across 328+ portals increases slightly; mitigated by using concurrent thread workers and efficient HTTP requests.

### Alternatives & Anti-Bot Mitigations
* **Headless Browser vs. Direct HTTP:** Running full headless browsers (`shot-scraper` / Playwright) sequentially across 328 portals would take 1.5 to 3 hours per daily run. Direct HTTP requests retrieve the full initial SSR HTML and API JSON payloads in seconds.
* **Future Bot Protection (Camoufox / Stealth):** If Axon or Netlify deploys anti-bot challenges (e.g., Cloudflare Error 1015 / Turnstile) in the future, anti-detect browser automation (such as Camoufox or Playwright-stealth, as employed in `scrape-flock-safety-subscriber-portals`) can be introduced. Currently, public endpoints respond directly without challenge.
