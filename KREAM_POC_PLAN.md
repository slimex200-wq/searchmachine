# KREAM PoC Plan

## Goal

Find one maintainable collection path for KREAM exhibition or promotion metadata.

The PoC is successful only if we can repeatedly collect:

- exhibition or promotion title
- canonical link
- date window if present
- short summary or event description

## Current State

Observed in this repository:

- direct web requests return `500`
- Playwright fallback returns tiny unusable HTML
- Cloudflare Browser Rendering is configured correctly
- Cloudflare rendering requests fail with `ReadTimeout`
- production scraper now marks the source as `disabled_cloudflare_timeout`

Interpretation:

- this is not a secrets problem
- this is not a parser-branch problem
- the current rendering provider and GitHub Actions runtime are insufficient for reliable KREAM collection

## Hypotheses

### Hypothesis 1

KREAM exhibition pages are reachable through a different rendering provider or execution environment.

### Hypothesis 2

Mobile app or mobile web uses structured APIs for exhibitions and promotions that are easier to automate than public storefront HTML.

### Hypothesis 3

Seller or partner flows may expose enough metadata to reduce the need for storefront scraping.

## PoC Order

Run the phases in this order:

1. Rendering provider comparison
2. Mobile-web and app network discovery
3. Partner or seller surface review

Do not spend more GitHub Actions-only effort on KREAM before phase 1 is completed.

## Phase 1: Rendering Provider Comparison

### Objective

Determine whether KREAM failure is specific to Cloudflare Browser Rendering or inherent to the target site.

### Test URLs

- `https://kream.co.kr/`
- `https://kream.co.kr/exhibitions`
- `https://kream.co.kr/search?keyword=크림`
- `https://kream.co.kr/search?keyword=스니커즈`

### What to compare

- time to first usable HTML
- final HTML size
- whether exhibition links appear
- whether title and text content are visible
- repeatability across at least 3 runs

### Desired outcome

- at least one provider returns stable HTML with exhibition content

### Failure criteria

- all providers time out or return unusable HTML
- only one-off success with no repeatability

## Phase 2: Mobile-Web and App Discovery

### Objective

Identify whether KREAM app or mobile web exposes exhibition metadata through structured APIs.

### Recommended environment

- local browser with developer tools
- Android emulator or physical device
- traffic inspection tool if needed

### Surfaces to inspect

- home page
- exhibitions list
- exhibition detail pages
- search pages for promotion terms

### Data to capture

- request URL
- method
- headers
- cookies
- app or device identifiers
- response type
- signature or token requirement

### Desired endpoint categories

- exhibitions list endpoint
- exhibition detail endpoint
- search endpoint with promotion metadata
- home banner feed

### Success criteria

- identify at least one structured endpoint for exhibition metadata
- replay locally more than once
- confirm whether auth or anti-bot tokens are stable enough for automation

### Failure criteria

- requests require strong runtime signatures
- encrypted responses or anti-automation controls block replay
- metadata is incomplete for event ingestion

## Phase 3: Partner or Seller Surface Review

### Objective

Check whether KREAM seller or partner flows can supply enough structured metadata to support event ingestion.

### Inputs

- partner center pages
- seller onboarding surfaces
- exhibition URLs visible on public pages

### Questions to answer

1. Are there sanctioned APIs or feeds for seller promotions?
2. Can partner surfaces provide promotion dates and links?
3. Is the access model compatible with this project?

### Deliverables

- candidate routes
- auth requirements
- usage assumptions
- go or no-go decision

## Data Model Target

Any successful path should be able to populate:

```text
platform
sale_name
start_date
end_date
link
description
image_url
source_type
```

## Decision Matrix

| Outcome | Decision |
| --- | --- |
| Alternate rendering provider works reliably | build provider-backed collector |
| Mobile/app endpoint works and is replayable | build API-based scraper |
| Partner path provides usable metadata | build sanctioned connector |
| None of the above works | keep KREAM disabled |

## Implementation Notes For This Repo

If any path succeeds, implementation should follow this order:

1. add a probe script first
2. store HTML or raw API responses under a debug path
3. only then wire the successful method into [scrapers/kream.py](/c:/Users/slime/Desktop/picksale-ingestor/scrapers/kream.py)

Do not continue tuning the current GitHub Actions rendering path until a provider comparison proves it can work.

## Next Concrete Tasks

1. Compare at least two rendering providers outside GitHub Actions.
2. Inspect KREAM app or mobile web requests for exhibitions.
3. Review partner or seller surfaces for sanctioned access options.
