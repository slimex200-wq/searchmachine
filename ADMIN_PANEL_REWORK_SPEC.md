# Admin Panel Rework Spec

## Goal

관리자 패널을 단순 조회 화면이 아니라 실제 운영 도구로 정리한다.

핵심 목표:

- 상태 집계와 카드 표시 기준을 통일한다.
- 같은 행사에 대한 신규 수집, 업데이트, 중복을 운영자가 즉시 구분할 수 있게 한다.
- 카드가 항상 행사 기간, 대표 소스, 대표 이미지 기준으로 일관되게 보이게 한다.
- 과거 데이터와 병합 이슈를 수동으로 정리할 수 있는 도구를 제공한다.

## Scope

대상 화면:

- 관리자 대시보드
- 검토 목록
- 게시됨 목록
- 숨김 목록
- 반려 목록
- 중복 분석/병합 관련 화면

대상 데이터:

- `sales`
- 필요 시 `community_posts`

## Canonical State Model

UI 전체에서 아래 상태 정의를 공통으로 사용한다.

### Sales primary states

- `review_pending`
  - 조건: `review_status = 'pending'` and `publish_status != 'published'` and `publish_status != 'hidden'`
- `approved_draft`
  - 조건: `review_status = 'approved'` and `publish_status = 'draft'`
- `published`
  - 조건: `publish_status = 'published'`
- `hidden`
  - 조건: `publish_status = 'hidden'`
- `rejected`
  - 조건: `review_status = 'rejected'`

### Source classification

- `official`
  - 조건: `source_type` in `crawler`, `official`
- `news`
  - 조건: `source_type = 'news'`
- `community`
  - 조건: `source_type = 'community'`
- `signal`
  - 별도 필드가 있으면 사용, 없으면 `signal_type` 기준 파생

중요:

- 상태 집계와 소스 집계를 섞지 않는다.
- 예: `게시됨 8/29`와 `커뮤니티 8/15`는 서로 다른 분모를 가지면 안 된다.

## Dashboard Rules

대시보드 상단 탭, 요약 카드, 목록 카운트는 모두 같은 쿼리 규칙을 사용한다.

### Top counts

- `전체`: 현재 필터 대상 전체 row 수
- `검토`: `review_pending`
- `게시됨`: `published`
- `숨김`: `hidden`
- `반려`: `rejected`
- `승인됨(초안)`: `approved_draft`
- `커뮤니티`: `source_type = 'community'`
- `뉴스`: `source_type = 'news'`
- `공식`: `source_type in ('crawler', 'official')`

### Denominator rules

- 상태 카운트 denominator는 동일한 `sales` 대상 집합 기준이어야 한다.
- `community_posts`를 따로 보여줄 경우, denominator도 그 테이블 기준으로 별도 표기한다.
- 서로 다른 집합의 카운트를 한 줄에서 `x / total` 형태로 섞지 않는다.

## Card Rendering Rules

카드 1장은 항상 "행사 단위"를 기준으로 보여준다.

### Title

- 기본: `sale_name`
- 부제 또는 보조 문구에 `platform`, `category`, `source_type` 표시 가능

### Date display

- 카드 메인 날짜는 무조건 `start_date ~ end_date`
- 기사 발행일은 메인 날짜로 쓰지 않는다
- 기사 발행일은 별도 메타 배지나 툴팁으로만 표시

### Image priority

카드 배너/썸네일은 아래 우선순위로 결정:

1. 현재 행사 묶음 내 대표 row의 `image_url`
2. 같은 `event_key`를 가진 row 중 `image_url`이 있는 공식 소스 row
3. 플랫폼 로고 fallback

추가 규칙:

- `image_url`이 비어 있거나 깨지면 fallback 사용
- `image_url`은 cover 방식으로 렌더
- 카드에 이미지가 없을 때 로고 fallback이 자연스럽게 보이게

### Source badges

카드에 최소 아래 배지를 표시:

- `공식`
- `뉴스`
- `커뮤니티`
- `업데이트`
- `중복 가능`
- `기존 행사`
- `최신 기사 YYYY-MM-DD`

## Duplicate / Update UX

운영자가 같은 행사를 또 승인하지 않게 가시성을 높인다.

### Required fields shown on card

- `event_key`
- `matched_by`
- `existing_id`
- `latest_pub_date`
- `source_urls count`

### Required status badges

- `신규`
  - `inserted = true`
- `업데이트`
  - `updated = true`
- `중복 차단`
  - `duplicate = true`
- `기존 게시 있음`
  - 동일 `event_key`의 `published` row 존재

### Warning rules

- 동일 `platform + event_key`의 published row가 있으면 승인 버튼 근처에 경고 표시
- 동일 `platform + event_key`의 다른 draft row가 있으면 병합 권장 표시
- 동일 행사인데 source만 다른 경우 `공식/뉴스 병합 대상` 표시

## Source URLs UI

한 행사에 여러 출처가 붙는 구조를 관리자에서 확인 가능해야 한다.

필수 기능:

- `source_urls` 전체 목록 표시
- 대표 링크와 최신 기사 링크를 구분 표시
- 공식 링크 / 뉴스 링크 / 커뮤니티 링크 유형 분리
- 외부 링크는 새 탭으로 열기

권장 표시 예:

- 대표 링크
- 최신 기사 링크
- 공식 행사 링크
- 출처 N개 펼치기

## Event Key Visibility

`event_key`는 관리자에게 숨기지 않는다.

필수 기능:

- 카드 메타에 `event_key` 표시
- 클릭 시 복사 가능
- 같은 `event_key`의 모든 row 모아보기
- `event_key missing` 배지 표시

## Merge / Repair Tools

과거 데이터 정리를 위해 수동 도구가 필요하다.

### Required admin actions

- `event_key` 수동 입력/수정
- 두 row 병합
- 대표 row 변경
- 대표 이미지 row 선택
- 대표 링크 row 선택
- 기간(start/end) 수동 보정

### Merge behavior

- 병합 시 source_urls는 union
- 대표 image_url 재선정 가능
- 대표 latest_source_url 재선정 가능
- published/review 상태는 운영자가 선택

## Upsert Feedback Panel

관리자에서 해당 카드가 어떤 이유로 현재 상태가 되었는지 보여준다.

표시 항목:

- `inserted`
- `updated`
- `duplicate`
- `matched_by`
- `existing_id`
- `final_event_key`
- `latest_pub_date`
- `source_type`
- `signal_type`
- `importance_score`
- `filter_reason`

## Filtering / Sorting

운영자 기준으로 가장 필요한 정렬과 필터:

### Filters

- 상태
- 소스 유형
- 플랫폼
- `event_key` 유무
- 이미지 유무
- `updated recently`
- `duplicate / update / inserted`

### Sorts

- 등록일
- 최근 업데이트일
- 최신 기사일
- 중요도
- 플랫폼

## Recommended Data Contract

관리자 패널에서 사용 가능한 필드:

- `id`
- `platform`
- `sale_name`
- `start_date`
- `end_date`
- `event_key`
- `image_url`
- `source_type`
- `signal_type`
- `confidence_score`
- `importance_score`
- `filter_reason`
- `review_status`
- `publish_status`
- `latest_pub_date`
- `latest_source_url`
- `source_urls`
- `matched_by`
- `existing_id`
- `inserted`
- `updated`
- `duplicate`
- `created_at`
- `updated_at`

## Backfill Tasks

관리자 패널 수정과 별개로 과거 데이터 백필이 필요하다.

필수 백필:

- `event_key` 없는 기존 published row 채우기
- 같은 행사인데 분리된 row 재병합
- 이미지 없는 기존 row에 같은 event_key의 공식 row image_url 반영
- 기사 발행일만 들어간 날짜를 실제 행사 기간으로 보정

## Acceptance Criteria

- 상단 탭과 대시보드 카드 숫자가 같은 규칙으로 계산된다
- 같은 행사 업데이트는 새 카드보다 기존 카드 갱신으로 보인다
- 관리자 화면에서 왜 `신규/업데이트/중복`인지 바로 보인다
- 카드 날짜는 항상 행사 기간으로 보인다
- 공식 image_url이 있으면 카드에 배너가 뜬다
- 같은 행사의 여러 출처를 관리자에서 확인할 수 있다
- 과거 데이터도 event_key 기준으로 정리 가능하다

## Suggested Prompt For Lovable

```text
관리자 패널 전체를 운영용으로 재정리해.

목표:
- 상태 집계 기준을 통일
- 같은 행사에 대한 신규/업데이트/중복을 명확히 구분
- 카드에 행사 기간, 대표 이미지, 대표 소스, event_key를 일관되게 표시
- source_urls와 최신 기사 정보를 관리자에서 확인 가능하게
- 과거 데이터 병합/수정 도구 제공

반드시 반영할 것:
- review_status / publish_status 기준 canonical state model 적용
- 상단 탭 카운트와 대시보드 카운트 동일 규칙 적용
- event_key, latest_pub_date, latest_source_url, source_urls, image_url 활용
- 카드 배너는 image_url 우선, 없으면 플랫폼 로고 fallback
- 동일 event_key의 published row가 있으면 승인 전 경고
- inserted / updated / duplicate / matched_by / existing_id 시각화
- source_urls 펼침 UI
- event_key 없는 row 배지 표시
- 수동 병합/대표 row 변경/기간 보정 도구 제공

기존 디자인 톤은 유지하되, 정보 밀도는 높이고 운영자가 실수하지 않게 가시성을 올려줘.
```
