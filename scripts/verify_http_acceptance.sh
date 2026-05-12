#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${MEMORY_CORE_BASE_URL:-http://127.0.0.1:8765}}"

if [ -n "${PYTHON_BIN:-}" ]; then
  :
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(0 if sys.version_info[0] >= 3 else 1)'; then
  PYTHON_BIN="python"
else
  echo "Python 3 is required to verify HTTP acceptance." >&2
  exit 1
fi

echo "Checking $BASE_URL"
curl --fail --silent "$BASE_URL/health" > /tmp/memory_core_health.json

curl --fail --silent \
  -H "Content-Type: application/json" \
  -d '{"items":[{"user_id":"demo-user","memory_space":"personal","source_id":"linux-verify-001","content":"Linux acceptance flow is working.","source":"linux-verify","event_type":"raw_message","sender":"user","occurred_at":"2026-05-12T19:00:00+00:00"}]}' \
  "$BASE_URL/api/v1/write" > /tmp/memory_core_write.json

curl --fail --silent \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-05-12","user_id":"demo-user","memory_space":"personal","timezone":"UTC"}' \
  "$BASE_URL/api/v1/daily-recall" > /tmp/memory_core_daily_recall.json

curl --fail --silent \
  "$BASE_URL/api/v1/export?user_id=demo-user&memory_space=personal&format=json" > /tmp/memory_core_export.json

$PYTHON_BIN - <<'PY'
import json

def load_json(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)

health = load_json('/tmp/memory_core_health.json')
write_result = load_json('/tmp/memory_core_write.json')
daily_recall = load_json('/tmp/memory_core_daily_recall.json')
export_result = load_json('/tmp/memory_core_export.json')
accepted_count = write_result.get('accepted_count')
if accepted_count is None:
  accepted_count = write_result.get('written_count', 0)
daily_recall_count = None
daily_recall_grouped = None
if isinstance(daily_recall.get('daily_recall'), dict):
  daily_recall_count = daily_recall['daily_recall'].get('entry_count')
  daily_recall_grouped = daily_recall['daily_recall'].get('grouped')
if daily_recall_count is None:
  daily_recall_count = daily_recall.get('hit_count')
if daily_recall_grouped is None:
  daily_recall_grouped = daily_recall.get('results')

assert health.get('ok') is True or health.get('status') == 'ok', health
assert accepted_count >= 1, write_result
assert daily_recall.get('status') == 'ok', daily_recall
assert daily_recall_count is not None and daily_recall_count >= 1, daily_recall
assert isinstance(daily_recall_grouped, list), daily_recall
assert isinstance(export_result.get('items'), list), export_result

print(json.dumps({
    'health': health,
  'accepted_count': accepted_count,
  'daily_recall_count': daily_recall_count,
    'export_count': len(export_result.get('items') or []),
}, ensure_ascii=False, indent=2))
PY