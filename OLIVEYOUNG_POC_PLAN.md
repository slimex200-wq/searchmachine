# Olive Young PoC Plan

## Goal

Find one maintainable collection path for Olive Young sale, event, or plan-shop metadata.

The PoC is successful only if we can repeatedly collect:

- event or promotion title
- canonical link
- date window if present
- short description or plan-shop summary

## Current State

Observed in this repository:

- `https://www.oliveyoung.co.kr/store/main/getStoreMain.do` returns `403`
- `https://m.oliveyoung.co.kr/m/main/getMMain.do` returns `403`
- `https://www.oliveyoung.co.kr/store/event/getEventList.do` returns `403`
- `https://www.oliveyoung.co.kr/store/planshop/getPlanShopList.do` returns `403`
- browser fallback also lands on Olive Young error pages

Interpretation:

- current web requests are blocked before parser quality matters
- desktop and mobile web both appear protected
- browser fallback is not enough by itself

## Hypotheses

### Hypothesis 1

Olive Young affiliate or partner surfaces provide enough structured data to avoid storefront scraping.

### Hypothesis 2

Mobile app or mobile web uses structured event APIs that are easier to automate than storefront HTML.

### Hypothesis 3

Browser automation with residential IP and persistent session can load event or plan-shop pages, but only with stronger session realism.

## PoC Order

Run the phases in this order:

1. Official and partner path discovery
2. Mobile-web and app network discovery
3. Residential browser validation

Do not start phase 3 until phases 1 and 2 fail or prove insufficient.

## Phase 1: Official and Partner Path Discovery

### Objective

Confirm whether Olive Young has an official, affiliate, or partner-sanctioned route that can expose event metadata.

### Inputs

- Olive Young affiliate or shopping curator guides
- public event and plan-shop pages
- partner or marketing landing flows if reachable

### Questions to answer

1. Does any official partner route expose event or plan-shop links in a structured way?
2. Is there a sanctioned product feed that can approximate event coverage?
3. What approval, login, or rate limits apply?

### Deliverables

- list of official endpoint or feed candidates
- auth requirements
- usage assumptions
- go or no-go decision for official path

### Exit criteria

Move to phase 2 if:

- no official route exists for event-level metadata
- or official route exists but cannot cover event list and detail fields

## Phase 2: Mobile-Web and App Discovery

### Objective

Identify whether Olive Young mobile clients expose event, plan-shop, or banner metadata through structured APIs.

### Recommended environment

- local browser with developer tools
- Android emulator or physical device
- traffic inspection tool if needed

### Pages and flows to inspect

- mobile main page
- event list page
- event detail page
- plan-shop list page
- plan-shop detail page
- app home banners and category banners

### Data to capture

- request URL
- method
- headers
- cookies
- app or device identifiers
- response type
- signature or token requirement

### Desired endpoint categories

- event list endpoint
- plan-shop list endpoint
- event detail endpoint
- plan-shop detail endpoint
- home banner feed

### Success criteria

- identify at least one structured endpoint for event or plan-shop metadata
- replay locally more than once
- confirm whether tokens are static, refreshable, or short-lived

### Failure criteria

- requests require tightly coupled device signatures
- responses are encrypted or inaccessible outside app runtime
- data does not contain usable event metadata

## Phase 3: Residential Browser Validation

### Objective

Check whether a real browser plus Korean residential IP can load Olive Young event surfaces consistently enough to justify scraper engineering.

### Recommended setup

- dedicated VM or always-on server
- Playwright or equivalent real browser automation
- Korean residential proxy with sticky session
- persistent browser profile and cookies

### Minimum experiment

1. visit mobile main page
2. visit event list
3. visit plan-shop list
4. open at least one detail page from each surface

### What to record

- final URL
- screenshot
- HTML length
- whether event cards are visible
- whether the page redirects to an error or verification state
- whether cookies or session reuse improve results

### Success criteria

- 3 consecutive successful list-page loads across 2 separate sessions
- detail page content visible in DOM

### Failure criteria

- repeated WAF challenge or verification loop
- unstable DOM requiring manual rescue
- no meaningful improvement from session persistence

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
| Official or affiliate path covers event metadata | build sanctioned connector |
| Mobile/app endpoint works and is replayable | build API-based scraper |
| Browser + residential proxy works reliably | build dedicated browser collector |
| None of the above works | keep Olive Young disabled |

## Implementation Notes For This Repo

If phase 2 or 3 succeeds, implementation should follow this order:

1. add a small standalone probe script first
2. save raw responses and HTML snapshots under a debug path
3. only then wire the successful method into [scrapers/oliveyoung.py](/c:/Users/slime/Desktop/picksale-ingestor/scrapers/oliveyoung.py)

Do not spend more time on selector tuning until access is solved.

## Next Concrete Tasks

1. Review Olive Young affiliate and partner-facing materials.
2. Inspect mobile web and app requests for event and plan-shop flows.
3. Decide whether a Korean residential browser experiment is justified.
