# Blocked Scraper Strategy

## Scope

This document covers the four currently blocked or unstable sources:

- KREAM
- Coupang
- Olive Young
- Ohouse

Current status in this repository:

- `KREAM`: disabled due to repeated Cloudflare Browser Rendering timeouts
- `Coupang`: disabled due to `403` access denial
- `Olive Young`: disabled due to `403` access denial
- `Ohouse`: disabled due to `403` and Akamai access denial

## Reference Links

- Coupang Open API guide: https://developers.coupangcorp.com/hc/en-us/article_attachments/360054636091
- Olive Young shopping curator guide: https://m.oliveyoung.co.kr/m/mtn/affiliate/guide
- KREAM notice on macro/API misuse restrictions: https://kream.co.kr/notice/378

## Operating Principle

Use this decision order for each blocked platform:

1. Prefer official or partner-sanctioned data access.
2. If unavailable, validate whether mobile-app or browser-rendered collection is technically possible.
3. Only invest in heavy anti-bot infrastructure for sources that materially improve product coverage.
4. Keep unstable sources explicitly disabled in production until a repeatable collection path exists.

## Strategy Table

| Platform | Current block pattern | Official path | Practical non-official path | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| KREAM | Web `500`, Cloudflare rendering `ReadTimeout` | No clear public event API confirmed; platform is sensitive to automated access | Mobile-app traffic analysis or residential browser automation | High | Keep disabled now; do not scale scraping until a dedicated PoC succeeds |
| Coupang | Web `403` on all seed URLs | Coupang Open API exists, but it is not an obvious public event/promotions feed | Browser automation with residential proxy and persistent session | High | First verify whether affiliate or seller-facing metadata can cover event use cases; otherwise run infrastructure PoC |
| Olive Young | Web `403`, browser error page | No public promotions API confirmed; affiliate path exists but is not event ingestion | Mobile-web/app API analysis plus Korean residential proxy | High | Treat as blocked source; run app/API discovery PoC before any large scraper work |
| Ohouse | Web `403`, Akamai access denied | No public event ingestion API confirmed | Mobile-app or signed API discovery plus anti-bot browser | High | Only pursue if business value is strong; Akamai usually implies higher maintenance cost |

## Recommended Priority

1. Coupang
2. Olive Young
3. Ohouse
4. KREAM

Reasoning:

- `Coupang` and `Olive Young` are likely to produce the highest event volume.
- `Ohouse` is valuable but anti-bot cost is likely higher.
- `KREAM` is currently the least promising from a stability-to-effort perspective because even Cloudflare rendering is timing out.

## Platform Notes

### KREAM

Observed in current workflow:

- origin requests return `500`
- Playwright fallback returns tiny unusable HTML
- Cloudflare Browser Rendering is configured correctly
- Cloudflare request fails with `ReadTimeout` across all seed URLs

Interpretation:

- This is no longer a secrets or fallback-branch problem.
- The current rendering provider and execution environment are not sufficient for reliable KREAM capture.

Operational stance:

- Keep `KREAM` explicitly disabled with `failure_reason=disabled_cloudflare_timeout`.
- Do not keep iterating on GitHub Actions-only rendering.

### Coupang

Observed in current workflow:

- all seed URLs return `403`

Interpretation:

- This is direct access denial, not parser failure.
- HTML parsing improvements alone will not help.

Operational stance:

- Keep disabled.
- Validate whether official partner flows can expose campaign metadata before building heavier scraping infrastructure.

### Olive Young

Observed in current workflow:

- all seed URLs return `403`
- browser fallback also lands on an error page

Interpretation:

- This is likely stronger request fingerprinting or bot blocking.

Operational stance:

- Keep disabled.
- Prioritize app/API discovery over more web-selector work.

### Ohouse

Observed in current workflow:

- all seed URLs return `403`
- logs show `akamai_access_denied`

Interpretation:

- This is the clearest WAF/CDN block among the four.

Operational stance:

- Keep disabled unless product value justifies a more expensive collection route.

## PoC Design

Each PoC should answer one question only:

Can we collect stable event-level sale metadata for this platform with a maintainable cost?

Success criteria for every PoC:

- fetch at least 5 relevant events or campaigns
- extract title, link, date window, and one description field
- repeat successfully across 3 runs on different days
- produce less than 20 percent hard failures

### PoC A: Official / Partner Path Discovery

Goal:

- determine whether the platform exposes an official, sanctioned, or quasi-official route that can replace scraping

Work items:

1. review official developer, affiliate, seller, and partner documentation
2. inspect public web traffic for JSON feeds used by event/list pages
3. check whether campaign metadata is available through partner landing APIs rather than storefront HTML

Outputs:

- documented endpoint candidates
- auth requirements
- allowed usage assumptions
- go/no-go decision

Best fit:

- Coupang
- Olive Young

### PoC B: Mobile App / Mobile Web API Discovery

Goal:

- verify whether the mobile client exposes event lists through JSON APIs that are easier to stabilize than desktop web

Method:

1. inspect mobile app or mobile web requests
2. identify event list, exhibition list, promotion detail, and search endpoints
3. capture headers, device identifiers, and anti-bot tokens
4. test replay from a local machine before moving to automation

Outputs:

- endpoint map
- required headers/cookies
- token lifetime notes
- repeatability assessment

Best fit:

- Olive Young
- Ohouse
- KREAM

### PoC C: Residential Browser Automation

Goal:

- verify whether a real browser plus clean residential IP and sticky session can load campaign pages consistently

Method:

1. run Playwright on a dedicated VM, not GitHub Actions
2. use residential proxy with sticky session
3. persist cookies and local storage between runs
4. add screenshots and HTML snapshots for every failed navigation

Success threshold:

- 3 consecutive successful event-list loads
- at least 1 detail page extract per platform

Best fit:

- Coupang
- Olive Young
- Ohouse

Warning:

- this is operationally expensive
- maintenance cost will be ongoing

### PoC D: Rendering Provider Comparison

Goal:

- determine whether KREAM failure is specific to Cloudflare Browser Rendering or inherent to the target

Method:

1. run the same KREAM URLs through at least 2 rendering providers
2. compare:
   - time to first HTML
   - final HTML size
   - whether event/exhibition links appear
3. keep the test isolated from parser logic

Outputs:

- provider comparison table
- timeout profile
- pass/fail recommendation

Best fit:

- KREAM only

## Suggested Build Order

### Phase 1

- keep all four disabled in production
- document current failure reasons in logs and dashboard
- run `Official / Partner Path Discovery` for Coupang and Olive Young

### Phase 2

- run `Mobile App / Mobile Web API Discovery` for Olive Young and Ohouse
- run `Rendering Provider Comparison` for KREAM

### Phase 3

- if still needed, run `Residential Browser Automation` for Coupang and Olive Young

## Repo Follow-up Tasks

1. Add a central disabled-source registry so blocked sources are explicitly visible.
2. Surface source disable reason in admin or summary reporting.
3. Keep KREAM, Coupang, Olive Young, and Ohouse out of quality metrics while disabled.
4. Re-enable a source only after a PoC shows stable extraction across multiple runs.

## Immediate Recommendation

- Production: keep all four disabled.
- Research next: start with `Coupang` and `Olive Young`.
- Infrastructure experiments: do not spend more GitHub Actions effort on KREAM until provider comparison is done.
