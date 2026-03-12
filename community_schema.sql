-- community_posts table (raw community ingestion)
create table if not exists public.community_posts (
  id bigint generated always as identity primary key,
  source_site text not null,              -- e.g. ppomppu
  source_board text,
  title text not null,
  body_preview text,
  link text not null unique,
  post_date timestamptz,
  collected_at timestamptz default now(),
  inferred_platform text,
  relevance_score int default 0,
  review_status text default 'pending',   -- pending/approved/rejected/promoted
  reviewed_by uuid,
  reviewed_at timestamptz,
  review_note text,
  promoted_sale_id bigint,
  raw_payload jsonb
);

create index if not exists idx_community_posts_review_status
  on public.community_posts(review_status);

create index if not exists idx_community_posts_inferred_platform
  on public.community_posts(inferred_platform);

create index if not exists idx_community_posts_relevance_score
  on public.community_posts(relevance_score desc);

-- Suggested RLS baseline
alter table public.community_posts enable row level security;

-- Public insert via edge function only is recommended; do not expose direct public insert unless needed.
-- Read/update/delete should be admin-only.
