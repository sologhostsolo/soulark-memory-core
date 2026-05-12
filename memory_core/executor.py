import re
from datetime import datetime
from typing import Any, Dict, List, Sequence

from memory_core.store import SQLiteMemoryStore


class MemoryCoreExecutor:
    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def search(
        self,
        *,
        query: str,
        limit: int = 20,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        return self.store.search(
            query=query,
            limit=limit,
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )

    def date_recall(
        self,
        *,
        day: str,
        limit: int = 50,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        timezone_name: str = "UTC",
    ) -> Dict[str, Any]:
        result = self.store.date_recall(
            day=day,
            limit=limit,
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
            timezone_name=timezone_name,
        )
        target_dates = [str(day or "").strip()] if str(day or "").strip() else []
        filtered_hits = self._filtered_results(result.get("hits"), target_dates)
        filtered_count = max(0, len(result.get("hits") or []) - len(filtered_hits))
        result["hits"] = filtered_hits
        result["evidence"] = self._evidence_from_hits(filtered_hits)
        result["hit_count"] = len(filtered_hits)
        result["miss_reason"] = "" if filtered_hits else "no_results"
        result["date_scope"] = self._date_scope(target_dates, filtered_count)
        return result

    def daily_recall(
        self,
        *,
        day: str,
        limit: int = 50,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        timezone_name: str = "UTC",
    ) -> Dict[str, Any]:
        result = self.date_recall(
            day=day,
            limit=limit,
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
            timezone_name=timezone_name,
        )
        result["mode"] = "daily_recall"
        daily_recall = self._build_daily_recall(result.get("hits"), day)
        if not daily_recall:
            daily_recall = {
                "target_dates": [str(day or "").strip()],
                "entry_count": 0,
                "grouped": [],
                "evidence": [],
                "render_instruction": "No reliable daily entries were found for the requested date.",
            }
        result["daily_recall"] = daily_recall
        return result

    @staticmethod
    def _filtered_results(hits: Any, target_dates: Sequence[str]) -> List[Dict[str, Any]]:
        items = hits if isinstance(hits, list) else []
        if not target_dates:
            return [dict(item) for item in items if isinstance(item, dict)]
        targets = {str(value or "").strip() for value in target_dates if str(value or "").strip()}
        filtered: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            event_date = str(item.get("event_date") or item.get("record_date") or "").strip()
            content = str(item.get("raw_content") or item.get("content") or "").strip()
            if event_date in targets and not MemoryCoreExecutor._mentions_non_target_date(content, targets):
                filtered.append(dict(item))
        return filtered

    @staticmethod
    def _date_scope(target_dates: Sequence[str], filtered_count: int) -> Dict[str, Any]:
        values = [str(value or "").strip() for value in target_dates if str(value or "").strip()]
        if not values:
            return {"enabled": False, "target_dates": [], "strict": False, "filtered_count": 0}
        return {
            "enabled": True,
            "target_dates": values,
            "strict": True,
            "filtered_count": int(filtered_count or 0),
            "policy": (
                "Only evidence whose event_date or record_date is one of target_dates may answer this turn. "
                "Do not use adjacent, recent, previous, or next-day evidence as a substitute."
            ),
        }

    @staticmethod
    def _mentions_non_target_date(text: str, target_dates: Sequence[str]) -> bool:
        raw = str(text or "")
        if not raw:
            return False
        targets = {str(value or "").strip() for value in target_dates if str(value or "").strip()}
        mentioned: List[str] = []
        for match in re.finditer(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?", raw):
            mentioned.append(f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}")
        for match in re.finditer(r"(?<!\d)(\d{1,2})月(\d{1,2})[日号]?", raw):
            years = {int(value[:4]) for value in targets if re.match(r"^20\d{2}-\d{2}-\d{2}$", value)}
            year = min(years) if len(years) == 1 else datetime.now().year
            mentioned.append(f"{year:04d}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
        return any(value and value not in targets for value in mentioned)

    @staticmethod
    def _evidence_from_hits(hits: Any) -> List[Dict[str, Any]]:
        items = hits if isinstance(hits, list) else []
        evidence: List[Dict[str, Any]] = []
        for hit in items:
            if not isinstance(hit, dict):
                continue
            hit_evidence = hit.get("evidence") if isinstance(hit.get("evidence"), list) else []
            for item in hit_evidence:
                if isinstance(item, dict):
                    evidence.append(item)
        return evidence

    @staticmethod
    def _build_daily_recall(hits: Any, day: str) -> Dict[str, Any]:
        items = hits if isinstance(hits, list) else []
        target_dates = [str(day or "").strip()] if str(day or "").strip() else []
        if not target_dates:
            return {}
        entries: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").strip()
            if source not in {
                "timeline_event",
                "timeline_episode",
                "timeline_material",
                "raw_message",
                "assistant_reply",
                "minimal_chat_raw",
                "daily_digest",
                "memory_entry",
            }:
                continue
            event_date = str(item.get("event_date") or item.get("record_date") or "").strip()
            if event_date not in target_dates:
                continue
            raw_content = str(item.get("raw_content") or item.get("content") or "").strip()
            if not raw_content:
                continue
            event_type = str(item.get("event_type") or "").strip()
            if event_type and event_type not in {"raw_message", "assistant_reply", "minimal_chat_raw", "daily_digest", "memory_entry"}:
                continue
            category = str(item.get("category") or "").strip()
            record_time = str(item.get("record_time") or "").strip()
            is_summary = event_type == "daily_digest" or category in {"event_log_daily", "nightly_reflection"}
            entries.append(
                {
                    "date": event_date,
                    "time": record_time,
                    "period": "daily_summary" if is_summary else MemoryCoreExecutor._period(record_time),
                    "actor": "system_summary" if is_summary else str(item.get("sender") or event_type or source).strip(),
                    "event_type": event_type,
                    "category": category,
                    "is_system_summary": is_summary,
                    "source": source,
                    "content": raw_content[:180],
                }
            )
        if not entries:
            return {}
        entries.sort(key=lambda value: (str(value.get("date") or ""), str(value.get("time") or ""), str(value.get("content") or "")))
        grouped: List[Dict[str, Any]] = []
        for period in ["daily_summary", "late_night", "morning", "noon", "afternoon", "evening", "unknown_time"]:
            rows = [entry for entry in entries if entry.get("period") == period]
            if rows:
                grouped.append({"period": period, "count": len(rows), "items": rows[:8]})
        return {
            "target_dates": target_dates,
            "entry_count": len(entries),
            "grouped": grouped,
            "evidence": entries[:24],
            "render_instruction": (
                "Answer day-recall questions from daily_recall first. "
                "Summarize what happened by period, mention exact HH:MM only when useful, "
                "and render daily summaries as summaries rather than user activities at that time."
            ),
        }

    @staticmethod
    def _period(record_time: str) -> str:
        text = str(record_time or "").strip()
        if len(text) >= 16 and text[10] == "T":
            text = text[11:16]
        if len(text) < 5 or ":" not in text:
            return "unknown_time"
        try:
            hour = int(text[:2])
        except Exception:
            return "unknown_time"
        if 0 <= hour < 6:
            return "late_night"
        if 6 <= hour < 11:
            return "morning"
        if 11 <= hour < 13:
            return "noon"
        if 13 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 24:
            return "evening"
        return "unknown_time"