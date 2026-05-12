import re
from typing import Any, Dict, List


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _first_text(items: List[Dict[str, Any]], *keys: str) -> str:
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return ""


def _date_from_text(value: str) -> str:
    text = str(value or "")
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    return match.group(1) if match else ""


def _looks_like_miss(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    markers = (
        "未找到",
        "没有找到",
        "暂无",
        "查不到",
        "没查到",
        "不确定",
        "不知道",
        "not found",
        "no hit",
        "no_hit",
        "no memory",
    )
    return any(marker in lowered for marker in markers)


def _evidence_from_hits(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for hit in _as_list(result.get("hits"))[:8]:
        if not isinstance(hit, dict):
            continue
        for item in _as_list(hit.get("evidence")):
            if isinstance(item, dict):
                evidence.append(item)
    return evidence


def _normalized_route(tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> str:
    for value in (
        result.get("route"),
        result.get("source"),
        arguments.get("route"),
        arguments.get("mode"),
        tool_name,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return tool_name


def _normalized_answer_kind(tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any], evidence: List[Dict[str, Any]]) -> str:
    for value in (result.get("answer_kind"), arguments.get("anchor"), arguments.get("mode")):
        text = str(value or "").strip()
        if text:
            return text
    for item in evidence:
        if not isinstance(item, dict):
            continue
        text = str(item.get("answer_kind") or "").strip()
        if text:
            return text
    return tool_name if tool_name in {"date_recall", "daily_recall"} else ""


def normalize_memory_evidence(*, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    result = result if isinstance(result, dict) else {}
    arguments = arguments if isinstance(arguments, dict) else {}
    evidence = [item for item in _as_list(result.get("evidence")) if isinstance(item, dict)]
    if not evidence:
        evidence = _evidence_from_hits(result)
    rendered_reply = str(result.get("result") or "").strip()
    confidence = 0.0
    if evidence:
        confidence = max(_safe_float(item.get("info_weight"), 0.0) for item in evidence)
    daily_recall = _as_dict(result.get("daily_recall"))
    date_scope = _as_dict(result.get("date_scope"))
    raw_count = _safe_int(result.get("raw_count"), 0) or _safe_int(result.get("hit_count"), 0) or _safe_int(daily_recall.get("entry_count"), 0) or len(evidence)

    miss_reason = str(result.get("miss_reason") or "").strip()
    if miss_reason and not evidence:
        status = "not_found"
    elif not evidence and _looks_like_miss(rendered_reply):
        status = "not_found"
    elif evidence and confidence >= 0.65:
        status = "found"
    elif evidence or rendered_reply:
        status = "weak"
    else:
        status = "not_found"

    snippet = _first_text(evidence, "content", "snippet", "text")
    if not snippet:
        snippet = rendered_reply[:500]
    time_text = _first_text(evidence, "time", "record_time", "date_text")
    date_text = str(arguments.get("date") or _first_text(evidence, "date", "record_date")).strip()
    if not date_text:
        date_text = _date_from_text(time_text) or _date_from_text(snippet)
    route = _normalized_route(tool_name, arguments, result)
    answer_kind = _normalized_answer_kind(tool_name, arguments, result, evidence)

    return {
        "tool": tool_name,
        "status": status,
        "source": str(result.get("source") or route),
        "route": route,
        "answer_kind": answer_kind,
        "time": time_text,
        "date": date_text,
        "snippet": snippet,
        "raw_count": raw_count,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "required_slot": "",
        "evidence_kind": "direct_fact" if evidence else "related_context",
        "miss_reason": miss_reason,
        "date_scope": date_scope,
        "daily_recall": daily_recall if tool_name in {"date_recall", "daily_recall"} else {},
        "evidence": evidence[:5],
        "rendered_reply": rendered_reply,
    }