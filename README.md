# PickSale Ingestor

## Pipeline

`main.py` runs sources in this order:
1. OliveYoungScraper (official -> sales)
2. MusinsaScraper (official -> sales)
3. OhouseScraper (official -> sales)
4. PpomppuCommunity (community -> community_posts)

Stages are separated as:
- scrape
- normalize
- classify_sale_importance
- filter_major_sales
- group_sale_events
- dedupe
- upload

Community data is never auto-promoted to sales when `ENABLE_COMMUNITY_PROMOTION=false`.
Default publishing target is grouped events with `sale_tier=major`.

## Engine Modules

The Sale Discovery Engine is under `app/core`:
- `models.py`: `SalePage`, `GroupedSaleEvent`
- `keyword_rules.py`: extendable keyword rule sets
- `sale_classifier.py`: score + tier classifier
- `sale_grouping.py`: merge related sale pages into one event
- `pipeline.py`: orchestrates normalize/classify/filter/group/dedupe/upload

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## .env example

```env
PICKSALE_SALES_API_URL=https://your-sales-edge-function-url
PICKSALE_COMMUNITY_API_URL=https://your-community-edge-function-url
PICKSALE_API_KEY=your-api-key
REQUEST_TIMEOUT_SECONDS=20
ENABLE_COMMUNITY_UPLOAD=true
ENABLE_COMMUNITY_PROMOTION=false
COMMUNITY_TARGET_PLATFORMS=쿠팡,올리브영,무신사,KREAM,SSG,오늘의집,29CM
DEBUG_SAVE_HTML=true
DEBUG_DIR=scraper_debug
```

## Run

```bash
python main.py
```

## Build EXE

Python is still required once to build the executable, but the built runner can be scheduled without calling `python.exe`.

```bash
pip install -r requirements-build.txt
build_picksale_exe.bat
```

Output:
- `dist\picksale_ingestor.exe`

## Windows Auto Run

`run_picksale.bat`:
- moves to project path
- runs `python main.py`
- appends logs to `logs\logs.txt`

`run_picksale_exe.bat`:
- moves to project path
- runs `dist\picksale_ingestor.exe`
- appends logs to `logs\logs.txt`

Task Scheduler quick setup:
1. Create Basic Task
2. Name: `PickSale Crawler`
3. Trigger: Daily
4. Add two triggers: e.g. `08:00` and `20:00`
5. Action: Start a program
6. Program/script: `C:\Users\slime\Desktop\picksale-ingestor\run_picksale_exe.bat`

If you still want the Python-based runner for local debugging:
1. Create Basic Task
2. Name: `PickSale Crawler (Python)`
3. Trigger: Daily
4. Add two triggers: e.g. `08:00` and `20:00`
5. Action: Start a program
6. Program/script: `C:\Users\slime\Desktop\picksale-ingestor\run_picksale.bat`

## GitHub Auto Run

If you want data collection to continue while your PC is off, use GitHub Actions instead of Windows Task Scheduler.

Workflow file:
- `.github/workflows/crawler.yml`

Current schedule:
- `08:00` KST
- `20:00` KST

The workflow also supports manual run from the GitHub Actions tab via `workflow_dispatch`.

Required GitHub repository secrets:
- `PICKSALE_SALES_API_URL`
- `PICKSALE_COMMUNITY_API_URL`
- `PICKSALE_API_KEY`
- `NAVER_CLIENT_ID` (optional, Naver news discovery only)
- `NAVER_CLIENT_SECRET` (optional, Naver news discovery only)

Setup steps:
1. Push this project to a GitHub repository.
2. Make sure the default branch exists as `main` after the first push.
3. In GitHub, open `Settings -> Secrets and variables -> Actions`.
4. Add `PICKSALE_SALES_API_URL`, `PICKSALE_COMMUNITY_API_URL`, and `PICKSALE_API_KEY`.
5. Add `NAVER_CLIENT_ID` and `NAVER_CLIENT_SECRET` only if you want Naver news ingestion enabled.
6. Open the `Actions` tab and enable workflows if prompted.
7. Run `PickSale Crawler` once manually to verify.

Suggested first push:
```bash
git init
git add .
git commit -m "Initial PickSale ingestor"
git branch -M main
git remote add origin https://github.com/<OWNER>/<REPO>.git
git push -u origin main
```

Notes:
- GitHub Actions is what runs the crawler, not Git itself.
- Scheduled workflows use UTC internally. The included cron values are already set for `08:00` and `20:00` KST.
- The workflow installs Playwright system dependencies on Ubuntu before running browser-backed scrapers.
- The crawler step writes both stdout and stderr to `crawler.log`, and the job now fails correctly if `main.py` exits non-zero.
- The workflow uploads `crawler.log` as an artifact after each run.

## Debug Diagnostics

- Each scraper logs:
  - requested URL
  - HTTP status
  - HTML length
  - selector count and fallback count
  - pre/post keyword filtering count
- If `DEBUG_SAVE_HTML=true`, HTML snapshots are stored in `scraper_debug/`.
