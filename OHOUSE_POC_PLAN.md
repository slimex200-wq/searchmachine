# Ohouse PoC Plan

## Goal

Find one maintainable collection path for Ohouse exhibition, event, or store promotion metadata.

The PoC is successful only if we can repeatedly collect:

- exhibition or promotion title
- canonical link
- date window if present
- short summary or event description

## Current State

Observed in this repository:

- `https://ohou.se/` returns `403`
- `https://contents.ohou.se/` returns `403`
- `https://contents.ohou.se/projects` returns `403`
- `https://ohou.se/store` returns `403`
- logs show `akamai_access_denied`
- browser fallback also fails with access denied behavior

Interpretation:

- this is a WAF or CDN access problem, not a parser problem
- selector tuning is irrelevant until access is solved

## Hypotheses

### Hypothesis 1

Ohouse store and exhibition surfaces expose structured data through mobile or store-specific APIs that are easier to reach than main web HTML.

### Hypothesis 2

Partner or seller flows exist that can reveal exhibition metadata without storefront scraping.

### Hypothesis 3

Residential browser automation can load store exhibition pages even when general web requests are blocked.

## PoC Order

Run the phases in this order:

1. Official and partner path discovery
2. Mobile-web and app network discovery
3. Residential browser validation

Do not start phase 3 until phases 1 and 2 fail or prove insufficient.

## Phase 1: Official and Partner Path Discovery

### Objective

Confirm whether Ohouse has any official or partner-facing route that can expose exhibition or promotion metadata.

### Inputs

- seller, advertiser, or partner pages if reachable
- store exhibition URLs visible on the public site
- any developer or feed documentation that can be found

### Questions to answer

1. Is there any official seller or partner route exposing exhibition lists?
2. Are exhibition pages indexed in predictable formats that can be tracked externally?
3. Does any sanctioned route provide enough metadata to avoid scraping?

### Deliverables

- list of official or partner candidates
- access requirements
- usage assumptions
- go or no-go decision

### Exit criteria

Move to phase 2 if:

- no sanctioned route exists
- or sanctioned routes do not expose usable exhibition metadata

## Phase 2: Mobile-Web and App Discovery

### Objective

Identify whether Ohouse app or mobile store surfaces expose exhibition metadata through structured APIs.

### Recommended environment

- local browser with developer tools
- Android emulator or physical device
- traffic inspection tool if needed

### Surfaces to inspect

- app home feed
- store home
- exhibition list pages
- exhibition detail pages
- banner and recommendation feeds

### Data to capture

- request URL
- method
- headers
- cookies
- device identifiers
- response format
- signature or token requirement

### Desired endpoint categories

- exhibition list endpoint
- exhibition detail endpoint
- home or store banner feed
- campaign recommendation feed

### Success criteria

- identify at least one structured endpoint carrying exhibition metadata
- replay locally more than once
- confirm whether auth or device signatures are stable enough for automation

### Failure criteria

- signatures are tightly coupled to runtime state
- responses are encrypted or obfuscated
- data lacks useful exhibition fields

## Phase 3: Residential Browser Validation

### Objective

Check whether a real browser plus Korean residential IP can load Ohouse store and exhibition surfaces reliably enough to justify engineering work.

### Recommended setup

- dedicated VM or always-on server
- Playwright or equivalent real browser automation
- Korean residential proxy with sticky session
- persistent browser profile and storage

### Minimum experiment

1. visit store home
2. visit at least one exhibition URL
3. attempt list-to-detail navigation
4. capture HTML, screenshot, and final URL

### What to record

- success or failure
- HTML size
- screenshot
- challenge or access-denied state
- whether cards and links are visible in DOM

### Success criteria

- 3 consecutive successful list or detail page loads
- exhibition metadata visible in DOM

### Failure criteria

- persistent Akamai block
- access loops that require manual intervention
- no useful DOM even after browser success

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
| Official or partner path works | build sanctioned connector |
| Mobile/app endpoint works and is replayable | build API-based scraper |
| Browser + residential proxy works reliably | build dedicated browser collector |
| None of the above works | keep Ohouse disabled |

## Implementation Notes For This Repo

If phase 2 or 3 succeeds, implementation should follow this order:

1. add a probe script first
2. save raw responses and HTML snapshots under a debug path
3. only then wire the successful method into [scrapers/ohouse.py](/c:/Users/slime/Desktop/picksale-ingestor/scrapers/ohouse.py)

Do not spend more time on current public-web selectors until access is solved.

## Next Concrete Tasks

1. Inspect whether store exhibition URLs follow stable patterns that can be tracked.
2. Inspect mobile app and store requests for exhibition metadata.
3. Decide whether a residential browser experiment is justified.
