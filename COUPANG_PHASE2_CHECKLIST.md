# Coupang Phase 2 Checklist

## Goal

Start phase 2 for Coupang:

- mobile-web discovery
- app traffic discovery
- structured endpoint identification

This checklist is intended for the first live discovery session.

## Precondition

Phase 1 outcome:

- public official Coupang docs do not currently solve event ingestion

Reference:

- [COUPANG_PHASE1_FINDINGS.md](/c:/Users/slime/Desktop/picksale-ingestor/COUPANG_PHASE1_FINDINGS.md)

## Session Objective

Answer one question:

Can Coupang mobile clients expose sale or campaign metadata through replayable structured requests?

## Environment

- local browser with devtools
- Android emulator or physical Android device
- optional traffic inspection tool
- account login only if strictly required

Do not use GitHub Actions for this phase.

## Surfaces To Inspect

### Mobile web

- mobile home
- Gold Box
- campaign list or event banner clicks
- promotion landing pages

### App

- app home banners
- Gold Box or equivalent limited-time sale surface
- campaign detail pages
- curated event tabs if present

## Requests To Capture

For every promising request, capture:

- URL
- method
- request headers
- cookies
- query params
- response body sample
- whether login is required
- whether a short-lived signature is present

## Endpoint Candidates To Prioritize

- home banner feed
- Gold Box feed
- campaign list feed
- campaign detail feed
- recommendation feed containing event cards

## Success Signals

The request is worth keeping if:

- response is JSON or GraphQL
- title and URL can be mapped
- date or remaining-time metadata exists
- replay works at least twice locally

## Failure Signals

Drop the request if:

- it only works once
- it depends on device-bound signatures
- it returns encrypted blobs
- it contains only product cards with no campaign identity

## Evidence To Save

Save the following in a local investigation folder:

- screenshots of target surfaces
- copied request as cURL
- one sanitized response sample
- notes about auth or anti-bot requirements

## Post-Session Output

At the end of the first session, produce:

1. endpoint shortlist
2. replayability assessment
3. go or no-go for implementation probe

## Implementation Gate

Do not modify [scrapers/coupang.py](/c:/Users/slime/Desktop/picksale-ingestor/scrapers/coupang.py) yet.

Only move to code when:

- at least one endpoint is replayable
- campaign metadata is present
- session stability is understood
