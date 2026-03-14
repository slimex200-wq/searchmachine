# Coupang App Discovery Guide

## Goal

Capture and evaluate Coupang mobile-app or mobile-web requests that may expose:

- Gold Box metadata
- campaign or event cards
- banner feeds
- promotion detail metadata

This guide is for the first real inspection session.

## What To Look For

Prioritize requests that return structured payloads with any of these fields:

- title or name
- deeplink or web URL
- image URL
- start date
- end date
- sale badge
- event identifier
- banner group identifier

Ignore requests that only contain:

- raw product inventory
- recommendations with no campaign identity
- analytics or telemetry

## Best Candidate Surfaces

Inspect in this order:

1. app home banner carousel
2. Gold Box or limited-time deal tab
3. campaign landing page opened from a banner
4. curated event tabs

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
signature_present:
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
- it works after a page refresh
- it does not require one-use signatures

A request is fragile if:

- it expires immediately
- it depends on per-device cryptographic signatures
- it breaks as soon as cookies rotate

## Fast Triage Rules

Keep the request if:

- response is JSON or GraphQL
- payload contains named sections like banner, exhibition, campaign, event, promotion, specialDeal, goldbox
- links are present in the payload

Drop the request if:

- payload is compressed or encrypted with no obvious structure
- payload only contains product IDs and ranking slots
- request depends on internal app RPC without readable metadata

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
- rich enough to build sale objects
