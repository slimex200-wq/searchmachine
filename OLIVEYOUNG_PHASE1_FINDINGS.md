# Olive Young Phase 1 Findings

## Scope

This note records phase 1 findings for Olive Young:

- official path review
- affiliate or sanctioned route review
- decision on whether phase 1 alone can solve event ingestion

## Sources Reviewed

- Olive Young shopping curator guide:
  https://m.oliveyoung.co.kr/m/mtn/affiliate/guide
- Olive Young affiliate earnings page:
  https://m.oliveyoung.co.kr/m/mtn/affiliate/earnings/request
- Olive Young public event list page:
  https://www.oliveyoung.co.kr/store/main/getEventList.do
- Olive Young public plan-shop detail example:
  https://www.oliveyoung.co.kr/store/planshop/getPlanShopDetail.do?dispCatNo=500000101480099&trackingCd=Cat10000020003_Planshop2_1_PROD

## Findings

### 1. A sanctioned affiliate path exists, but it is not an event-ingestion API

The visible sanctioned route is Olive Young's shopping curator program.

This appears useful for:

- tracked product sharing
- affiliate link attribution
- payout and activity workflows

It does not appear, from the reviewed public pages, to be a clearly documented public API for:

- event list retrieval
- plan-shop list retrieval
- event detail metadata feed

### 2. Public event and plan-shop surfaces do exist

Public Olive Young pages for:

- event lists
- plan-shop details

are visible on the web and indexable.

This matters because the metadata likely exists somewhere in Olive Young's own client flows, even though direct requests from this repository are blocked with `403`.

### 3. Publicly visible sanctioned documentation does not currently solve the repository use case

The current repository needs:

- title
- link
- date window
- description

for event-like sales objects.

The reviewed public affiliate materials do not appear sufficient to supply those fields in structured form.

This is an inference from the reviewed public materials, not a guarantee that no approval-gated partner route exists.

## Decision

Phase 1 result for Olive Young:

- `public sanctioned docs are not enough`
- move to phase 2 mobile-web and app discovery

## Recommendation

Do not spend more time on public affiliate pages as a primary ingestion strategy.

Next step should be:

1. inspect mobile web and app traffic for event and plan-shop surfaces
2. identify whether structured APIs exist behind those pages
3. only if that fails, consider residential browser validation
