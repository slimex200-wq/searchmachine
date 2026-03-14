# Olive Young App Discovery Guide

## Goal

Capture and evaluate Olive Young mobile-app or mobile-web requests that may expose:

- event list metadata
- event detail metadata
- plan-shop list metadata
- plan-shop detail metadata
- home banner metadata

This guide is for the first real inspection session.

## What To Look For

Prioritize requests that return structured payloads with any of these fields:

- title
- subtitle
- event name
- plan-shop name
- landing URL
- image URL
- start date
- end date
- promotion identifier

Ignore requests that only contain:

- user profile state
- telemetry
- personalized recommendation models with no event identity

## Best Candidate Surfaces

Inspect in this order:

1. app home banner feed
2. mobile event list
3. mobile event detail
4. mobile plan-shop list
5. mobile plan-shop detail

## Capture Format

For every promising request, save one record with these fields:

```text
surface:
trigger_action:
request_url:
method:
status_code:
content_type:
auth_headers:
custom_headers:
cookies_required:
cf_or_signature_tokens:
response_shape:
title_field_candidates:
url_field_candidates:
date_field_candidates:
image_field_candidates:
replay_result:
notes:
```

## Replay Rules

A request is replayable if:

- it works twice from the same session
- it works after route reload
- it does not require a one-shot challenge token

A request is fragile if:

- it depends on Cloudflare or anti-bot challenge state
- it requires short-lived headers tied to the app runtime
- it only works while an app session is actively open

## Fast Triage Rules

Keep the request if:

- response is JSON or GraphQL
- payload contains sections named event, planShop, exhibition, banner, promotion
- links or identifiers are visible in the payload

Drop the request if:

- response is only error-shell HTML
- request depends on constantly changing challenge headers
- payload has no event identity

## Output Checklist

At the end of the session, prepare:

1. endpoint shortlist with 3 or fewer best candidates
2. one sanitized payload sample per candidate
3. replayability rating:
   - stable
   - fragile
   - unusable
4. implementation recommendation:
   - build probe
   - inspect deeper
   - stop

## Implementation Gate

Only move into production implementation if at least one endpoint is:

- structured
- replayable
- rich enough to build event or plan-shop sale objects
