# SoulArk Memory Core API Contract

This is the stable v0.1 HTTP contract used by upper layers such as SoulArk Personal and future Work Memory demos.

Base URL in local development:

```text
http://127.0.0.1:8765
```

## Common Fields

Most write and recall calls accept these fields:

- `user_id`: caller-defined user id.
- `memory_space`: logical memory namespace, such as `personal`, `work`, or `demo`.
- `source_id`: optional upstream source id for traceability.
- `limit`: optional result limit. The server clamps it to a safe range.

## Health

```text
GET /health
```

Returns:

- `status`
- `database_path`

## Write

```text
POST /api/v1/write
```

Request:

```json
{
  "items": [
    {
      "user_id": "demo_user",
      "memory_space": "personal",
      "source_id": "msg-001",
      "content": "I tested SoulArk Memory Core today.",
      "source": "demo",
      "event_type": "raw_message",
      "sender": "user",
      "role": "user",
      "occurred_at": "2026-05-14T10:00:00+00:00"
    }
  ]
}
```

Stable response fields:

- `status`
- `memory_ids`
- `accepted_count`
- `rejected_count`
- `failure_reason`
- `items`

## Search

```text
POST /api/v1/search
```

Request:

```json
{
  "user_id": "demo_user",
  "memory_space": "personal",
  "query": "Memory Core",
  "limit": 5
}
```

Stable response fields:

- `status`
- `hits`
- `raw_count`
- `truncated`

Stable hit fields:

- `id`
- `content`
- `raw_content`
- `score`
- `source`
- `occurred_at`
- `record_date`
- `event_date`
- `record_time`
- `event_type`
- `category`
- `sender`
- `role`
- `source_type`
- `answer_kind`
- `title`
- `evidence`
- `user_id`
- `memory_space`
- `source_id`

## Date Recall

```text
POST /api/v1/date-recall
```

Request:

```json
{
  "user_id": "demo_user",
  "memory_space": "personal",
  "date": "2026-05-14",
  "timezone": "UTC",
  "limit": 10
}
```

Stable response fields:

- `status`
- `mode`
- `date`
- `timezone`
- `hits`
- `evidence`
- `hit_count`
- `truncated`
- `miss_reason`
- `date_scope`

Empty recall must return:

```json
{
  "hits": [],
  "evidence": [],
  "hit_count": 0,
  "miss_reason": "no_results"
}
```

## Daily Recall

```text
POST /api/v1/daily-recall
```

Daily recall returns the same outer recall shape as date recall, plus:

- `daily_recall`

Stable `daily_recall` fields:

- `date`
- `timezone`
- `target_dates`
- `entry_count`
- `grouped`

## Delete

```text
POST /api/v1/delete
```

Request:

```json
{
  "user_id": "demo_user",
  "memory_space": "personal",
  "ids": ["memory-id"]
}
```

Stable response fields:

- `status`
- `deleted_count`
- `not_found_count`
- `failure_reason`

## Export

```text
GET /api/v1/export?user_id=demo_user&memory_space=personal&format=json
```

Stable response fields:

- `status`
- `export_id`
- `count`
- `format`
- `filters`
- `items`

## Error Shape

Validation errors return:

- `status`: `error`
- `error_code`
- `message`

The current API intentionally stays small. New endpoints should not be added unless they strengthen the v0.1 memory loop.
