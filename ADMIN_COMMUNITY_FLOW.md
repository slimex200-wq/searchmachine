# Admin Structure Proposal

## Admin Tabs

1. `Sales`
- Existing published/draft sales management.
- Data source: `sales`.

2. `Community Inbox`
- Data source: `community_posts` with `review_status='pending'`.
- Columns: `source_site`, `title`, `inferred_platform`, `relevance_score`, `collected_at`, `link`.
- Actions:
  - `Approve as Sales Draft`: copy/promote to `sales` and mark `review_status='promoted'`.
  - `Reject`: set `review_status='rejected'`.
  - `Keep Pending`: no status change.

3. `Community Reviewed`
- Data source: `community_posts` with `review_status in ('promoted','rejected')`.
- Audit fields: `reviewed_by`, `reviewed_at`, `review_note`, `promoted_sale_id`.

## Promotion Rule (recommended)

- Promote only when:
  - `inferred_platform` in target set (`쿠팡, 올리브영, 무신사, KREAM, SSG, 오늘의집, 29CM`)
  - title/link quality is acceptable
- Insert to `sales` with:
  - `source_type='community'`
  - `status='draft'`
- Publish after admin verification.
