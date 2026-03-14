# Coupang Phase 1 Findings

## Scope

This note records phase 1 findings for Coupang:

- official API path review
- public partner or sanctioned route review
- decision on whether phase 1 alone can solve Coupang collection

## Sources Reviewed

- Coupang Open API guide:
  https://developers.coupangcorp.com/hc/en-us/article_attachments/360054636091
- Coupang API integration guide:
  https://developers.coupangcorp.com/hc/ko/article_attachments/360059110331
- Coupang developer portal notice listing available API families:
  https://developers.coupangcorp.com/hc/en-us/articles/48314250583705-Notice-of-changes-of-developer-portal-and-24-apis-s-internationalization-June-26-2025

## Findings

### 1. The visible official API surface is marketplace-oriented

The public developer materials reviewed are centered on:

- product creation and listing
- order and shipping workflows
- vendor integration
- marketplace operations

I did not find a clearly documented public API for:

- campaign list retrieval
- event list retrieval
- Gold Box metadata feed
- promotions landing page metadata

This is an inference from the reviewed public documentation, not a guarantee that no private or partner route exists.

### 2. Public official docs do not currently solve event ingestion

Based on the visible docs, the official API path does not appear sufficient for this repository's use case:

- title
- link
- date window
- description

for campaign or sale-event objects.

### 3. A sanctioned path may still exist outside the public developer docs

This remains possible through:

- affiliate programs
- partner dashboards
- internal or approval-gated feeds

But it was not confirmed in the public materials reviewed so far.

## Decision

Phase 1 result for Coupang:

- `official public docs are not enough`
- move to phase 2 mobile-web and app discovery

## Recommendation

Do not spend more time trying to force current public Coupang Open API docs into an event-ingestion role.

Next step should be:

1. inspect mobile web and app traffic for Gold Box and campaign surfaces
2. only if that fails, consider residential browser validation
