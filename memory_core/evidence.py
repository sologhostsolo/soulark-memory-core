import json
from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def build_timeline_evidence(item: Dict[str, Any], *, source_kind: str = "timeline_event") -> Dict[str, Any]:
    occurred_at = str(item.get("occurred_at") or "").strip()
    return {
        "content": str(item.get("content") or "").strip(),
        "record_time": occurred_at,
        "date_text": occurred_at[:10],
        "kind": source_kind,
        "source_type": _first_non_empty(item.get("source_type"), item.get("source"), "memory_core"),
        "answer_kind": _first_non_empty(item.get("answer_kind"), item.get("event_type"), "memory_entry"),
        "info_weight": round(max(0.0, min(1.0, _safe_float(item.get("info_weight"), 0.8))), 4),
        "source_id": _first_non_empty(item.get("source_id"), item.get("event_id"), item.get("id")),
        "memory_space": _first_non_empty(item.get("memory_space"), "personal"),
    }


def build_fact_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    occurred_at = str(item.get("occurred_at") or "").strip()
    info_weight = item.get("info_weight")
    if info_weight in (None, ""):
        info_weight = item.get("confidence")
    return {
        "content": str(item.get("content") or "").strip(),
        "record_time": occurred_at,
        "date_text": occurred_at[:10],
        "kind": "bio_fact",
        "source_type": _first_non_empty(item.get("source_type"), item.get("source"), "memory_core"),
        "answer_kind": _first_non_empty(item.get("answer_kind"), "fact"),
        "info_weight": round(max(0.0, min(1.0, _safe_float(info_weight, 0.85))), 4),
        "source_id": _first_non_empty(item.get("source_id"), item.get("source_ref"), item.get("id")),
        "memory_space": _first_non_empty(item.get("memory_space"), "personal"),
    }


def build_fact_slot_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    occurred_at = _first_non_empty(item.get("updated_at"), item.get("occurred_at"), item.get("created_at"))
    topic = str(item.get("topic") or "").strip()
    fact_key = str(item.get("fact_key") or "").strip()
    label = " / ".join(part for part in (topic, fact_key) if part)
    content = str(item.get("value_text") or item.get("content") or "").strip()
    return {
        "content": content,
        "record_time": occurred_at,
        "date_text": occurred_at[:10],
        "kind": "fact_slot",
        "source_type": _first_non_empty(item.get("source_type"), "memory_core"),
        "answer_kind": _first_non_empty(item.get("answer_kind"), "fact_slot"),
        "info_weight": round(max(0.0, min(1.0, _safe_float(item.get("info_weight"), 0.83))), 4),
        "source_id": _first_non_empty(item.get("source_id"), item.get("id")),
        "memory_space": _first_non_empty(item.get("memory_space"), "personal"),
        "slot_label": label,
    }


def build_search_hit(item: Dict[str, Any], *, score: float, source_kind: str) -> Dict[str, Any]:
    occurred_at = _first_non_empty(item.get("occurred_at"), item.get("updated_at"), item.get("created_at"))
    extra = _as_dict(item.get("extra_json"))
    content = str(item.get("content") or item.get("value_text") or "").strip()
    record_date = occurred_at[:10]
    evidence = [
        build_fact_evidence(item)
        if source_kind == "bio_fact"
        else build_fact_slot_evidence(item)
        if source_kind == "fact_slot"
        else build_timeline_evidence(item, source_kind=source_kind)
    ]
    return {
        "id": str(item.get("id") or "").strip(),
        "content": content,
        "raw_content": content,
        "score": round(max(0.0, min(1.0, _safe_float(score, 0.0))), 4),
        "source": source_kind,
        "occurred_at": occurred_at,
        "record_date": record_date,
        "event_date": _first_non_empty(item.get("logical_date"), extra.get("logical_date"), record_date),
        "record_time": occurred_at[11:16] if len(occurred_at) >= 16 else "",
        "event_type": str(item.get("event_type") or "").strip(),
        "category": str(item.get("category") or "").strip(),
        "sender": str(item.get("sender") or "").strip(),
        "role": str(item.get("role") or "").strip(),
        "source_type": _first_non_empty(item.get("source_type"), item.get("source")),
        "answer_kind": _first_non_empty(item.get("answer_kind"), item.get("event_type")),
        "title": str(item.get("title") or "").strip(),
        "evidence": evidence,
        "user_id": str(item.get("user_id") or "").strip(),
        "memory_space": str(item.get("memory_space") or "").strip(),
        "source_id": _first_non_empty(item.get("source_id"), item.get("event_id"), item.get("source_ref")),
        "trace_ref": str(item.get("trace_ref") or "").strip(),
        "info_weight": round(
            max(0.0, min(1.0, _safe_float(item.get("info_weight"), item.get("confidence", 0.0)))),
            4,
        ),
        "extra_json": extra,
    }


def build_recall_result(
    *,
    hits: List[Dict[str, Any]],
    day: str,
    timezone_name: str,
    mode: str,
    truncated: bool,
) -> Dict[str, Any]:
    evidence: List[Dict[str, Any]] = []
    for hit in hits:
        hit_evidence = hit.get("evidence") if isinstance(hit.get("evidence"), list) else []
        for item in hit_evidence:
            if isinstance(item, dict):
                evidence.append(item)
    return {
        "status": "ok",
        "mode": mode,
        "date": str(day or "").strip(),
        "timezone": str(timezone_name or "UTC").strip() or "UTC",
        "hits": hits,
        "evidence": evidence,
        "hit_count": len(hits),
        "truncated": bool(truncated),
        "miss_reason": "" if hits else "no_results",
    }


def build_export_item(item: Dict[str, Any], *, source_kind: str) -> Dict[str, Any]:
    payload = dict(item)
    payload["content"] = str(item.get("content") or item.get("value_text") or "").strip()
    payload["occurred_at"] = _first_non_empty(item.get("occurred_at"), item.get("updated_at"), item.get("created_at"))
    payload["source_id"] = _first_non_empty(item.get("source_id"), item.get("event_id"), item.get("source_ref"))
    payload["source"] = source_kind
    payload["evidence"] = [
        build_fact_evidence(item)
        if source_kind == "bio_fact"
        else build_fact_slot_evidence(item)
        if source_kind == "fact_slot"
        else build_timeline_evidence(item, source_kind=source_kind)
    ]
    return payload
