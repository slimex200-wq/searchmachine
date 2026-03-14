# Coupang PoC Plan

## Goal

Find one maintainable collection path for Coupang sale or campaign metadata.

The PoC is successful only if we can repeatedly collect:

- event or campaign title
- canonical link
- date window if present
- short description or campaign summary

## Current State

Observed in this repository:

- `https://www.coupang.com/` returns `403`
- `https://www.coupang.com/np/goldbox` returns `403`
- `https://pages.coupang.com/` returns `403`
- `https://www.coupang.com/np/campaigns` returns `403`

Interpretation:

- current desktop web requests are blocked before parser quality matters
- the immediate problem is access, not extraction logic

## Hypotheses

### Hypothesis 1

Coupang exposes enough useful metadata through an official or partner-facing path that we can avoid storefront scraping.

### Hypothesis 2

Desktop web is blocked, but browser automation with residential IP and persistent session can still load campaign surfaces.

### Hypothesis 3

Mobile web or app traffic exposes JSON endpoints that are easier to automate than storefront HTML.

## PoC Order

Run the phases in this order:

1. Official and partner path discovery
2. Mobile-web and app network discovery
3. Residential browser validation

Do not start phase 3 until phases 1 and 2 fail or prove insufficient.

## Phase 1: Official and Partner Path Discovery

### Objective

Confirm whether official Coupang interfaces can provide promotion or campaign-level metadata.

### Inputs

- Coupang Open API documentation
- affiliate, seller, or partner pages if accessible
- public marketing landing pages

### Questions to answer

1. Does any official API expose campaign, event, Gold Box, or promotion metadata?
2. If not directly, can partner URLs or feeds approximate event coverage?
3. What authentication or approval is required?

### Deliverables

- list of official endpoint candidates
- auth requirements
- allowed usage notes
- go or no-go decision for official path

### Exit criteria

Move to phase 2 if:

- no official route exists for event-level metadata
- or official route exists but cannot cover required fields

## Phase 2: Mobile-Web and App Discovery

### Objective

Identify whether Coupang mobile clients use JSON or GraphQL APIs for event surfaces.

### Recommended environment

- local browser with developer tools
- Android emulator or physical device
- traffic inspection tool if needed

### Pages to inspect

- mobile main page
- Gold Box
- promotions or campaigns landing page
- any event banners or exhibition pages reachable from the app

### Data to capture

- request URL
- method
- headers
- cookies
- query params
- response type
- token or signature requirement

### Desired endpoint categories

- event list endpoint
- campaign detail endpoint
- banner feed endpoint
- time-limited sale feed

### Success criteria

- identify at least one endpoint that returns structured promotion metadata
- replay the request locally more than once
- confirm token lifetime or refresh behavior

### Failure criteria

- requests require short-lived signatures tied to device state
- responses are encrypted or obfuscated
- data is incomplete for event use

## Phase 3: Residential Browser Validation

### Objective

Check whether a real browser plus residential IP can load blocked pages consistently enough to justify engineering work.

### Recommended setup

- dedicated VM or always-on server
- Playwright or another real browser automation framework
- Korean residential proxy with sticky sessions
- persistent browser profile

### Minimum experiment

1. visit main page
2. visit Gold Box
3. visit campaign list
4. capture HTML length, title, screenshot, and final URL

### What to record

- response success or failure
- time to load
- screenshot of final page
- HTML size
- whether event links are visible
- whether a login gate appears

### Success criteria

- at least 3 consecutive successful page loads across 2 separate sessions
- event links or structured campaign cards visible in DOM

### Failure criteria

- repeated WAF challenge
- CAPTCHA or human verification
- unstable page load requiring manual intervention

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
| Official path covers needed metadata | build official connector |
| Mobile/app endpoint works and is replayable | build API-based scraper |
| Browser + residential proxy works reliably | build dedicated browser collector |
| None of the above works | keep Coupang disabled |

## Implementation Notes For This Repo

If phase 2 or 3 succeeds, implementation should follow this order:

1. add a small standalone probe script first
2. save raw response examples under a debug path
3. only then wire the successful method into [scrapers/coupang.py](/c:/Users/slime/Desktop/picksale-ingestor/scrapers/coupang.py)

Do not rewrite the production scraper before a probe proves the path is stable.

## Next Concrete Tasks

1. Review official Coupang docs and note any campaign-related endpoints.
2. Inspect mobile web and app requests for Gold Box and campaign surfaces.
3. Decide whether a residential browser experiment is justified.
