import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

from memory_core.evidence import build_export_item, build_recall_result, build_search_hit


class SQLiteMemoryStore:
    def __init__(self, database_path: str):
        self.database_path = str(database_path or "data/memory_core.db").strip() or "data/memory_core.db"
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(self.database_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episodes ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "category TEXT NOT NULL DEFAULT 'general', "
                "content TEXT NOT NULL, "
                "source TEXT NOT NULL DEFAULT 'compact', "
                "extra_json TEXT NOT NULL DEFAULT '{}', "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_lookup "
                "ON episodes (user_id, memory_space, ts DESC, category)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS timeline_events ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "event_id TEXT NOT NULL DEFAULT '', "
                "event_type TEXT NOT NULL DEFAULT 'memory_entry', "
                "source_platform TEXT NOT NULL DEFAULT 'api', "
                "source_account TEXT NOT NULL DEFAULT '', "
                "message_id TEXT NOT NULL DEFAULT '', "
                "sender TEXT NOT NULL DEFAULT '', "
                "role TEXT NOT NULL DEFAULT '', "
                "msg_type TEXT NOT NULL DEFAULT 'text', "
                "content TEXT NOT NULL, "
                "source_type TEXT NOT NULL DEFAULT 'api', "
                "answer_kind TEXT NOT NULL DEFAULT 'memory_entry', "
                "is_question INTEGER NOT NULL DEFAULT 0, "
                "is_correction INTEGER NOT NULL DEFAULT 0, "
                "is_noise INTEGER NOT NULL DEFAULT 0, "
                "info_weight REAL NOT NULL DEFAULT 0.8, "
                "trace_ref TEXT NOT NULL DEFAULT '', "
                "extra_json TEXT NOT NULL DEFAULT '{}', "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_timeline_events_lookup "
                "ON timeline_events (user_id, memory_space, ts DESC, event_type)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS event_references ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "source_event_id TEXT NOT NULL DEFAULT '', "
                "target_event_id TEXT NOT NULL DEFAULT '', "
                "reference_type TEXT NOT NULL DEFAULT 'timeline_quote', "
                "reason TEXT NOT NULL DEFAULT '', "
                "score REAL NOT NULL DEFAULT 0.0, "
                "extra_json TEXT NOT NULL DEFAULT '{}', "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_references_lookup "
                "ON event_references (user_id, memory_space, ts DESC, source_event_id)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS bio_facts ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "category TEXT NOT NULL DEFAULT 'personal', "
                "content TEXT NOT NULL, "
                "confidence REAL NOT NULL DEFAULT 1.0, "
                "memory_type TEXT NOT NULL DEFAULT 'fact', "
                "subtype TEXT NOT NULL DEFAULT '', "
                "source_ref TEXT NOT NULL DEFAULT '', "
                "status TEXT NOT NULL DEFAULT 'active', "
                "source_type TEXT NOT NULL DEFAULT 'api', "
                "answer_kind TEXT NOT NULL DEFAULT 'fact', "
                "is_question INTEGER NOT NULL DEFAULT 0, "
                "is_correction INTEGER NOT NULL DEFAULT 0, "
                "is_noise INTEGER NOT NULL DEFAULT 0, "
                "info_weight REAL NOT NULL DEFAULT 0.85, "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_bio_facts_lookup "
                "ON bio_facts (user_id, memory_space, ts DESC, status)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS fact_slots ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "topic TEXT NOT NULL, "
                "fact_key TEXT NOT NULL, "
                "value_text TEXT NOT NULL, "
                "value_type TEXT NOT NULL DEFAULT 'text', "
                "normalized_value TEXT NOT NULL DEFAULT '', "
                "source_fact_id TEXT NOT NULL DEFAULT '', "
                "confidence REAL NOT NULL DEFAULT 1.0, "
                "status TEXT NOT NULL DEFAULT 'active', "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_fact_slots_lookup "
                "ON fact_slots (user_id, memory_space, topic, fact_key, status, ts DESC)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS distillation_materials ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "memory_space TEXT NOT NULL DEFAULT 'personal', "
                "source_id TEXT NOT NULL DEFAULT '', "
                "ts INTEGER NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "source_type TEXT NOT NULL, "
                "title TEXT NOT NULL DEFAULT '', "
                "content TEXT NOT NULL, "
                "source_ref TEXT NOT NULL DEFAULT '', "
                "weight REAL NOT NULL DEFAULT 1.0, "
                "quality REAL NOT NULL DEFAULT 1.0, "
                "used_in_version TEXT NOT NULL DEFAULT '', "
                "status TEXT NOT NULL DEFAULT 'active', "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_distillation_materials_lookup "
                "ON distillation_materials (user_id, memory_space, source_type, status, ts DESC)"
            )
            connection.commit()

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _normalize_scope(user_id: str = "", memory_space: str = "", source_id: str = "") -> Tuple[str, str, str]:
        normalized_user_id = str(user_id or "default").strip() or "default"
        normalized_space = str(memory_space or "personal").strip() or "personal"
        normalized_source_id = str(source_id or "").strip()
        return normalized_user_id, normalized_space, normalized_source_id

    @classmethod
    def _normalize_occurred_at(cls, value: Any) -> Tuple[str, int]:
        raw = str(value or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        if not raw:
            parsed = datetime.now(timezone.utc)
        else:
            try:
                if len(raw) == 10:
                    parsed = datetime.combine(
                        datetime.strptime(raw, "%Y-%m-%d").date(),
                        time.min,
                        tzinfo=timezone.utc,
                    )
                else:
                    parsed = datetime.fromisoformat(raw)
            except ValueError:
                parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        normalized = parsed.astimezone(timezone.utc).replace(microsecond=0)
        return normalized.isoformat(), int(normalized.timestamp())

    @staticmethod
    def _json_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value if value is not None else {}, ensure_ascii=False)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    @staticmethod
    def _build_scope_clauses(
        *,
        user_id: str,
        memory_space: str,
        source_id: str,
        user_required: bool = False,
    ) -> Tuple[List[str], List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if user_id or user_required:
            clauses.append("user_id = ?")
            params.append(user_id or "default")
        if memory_space:
            clauses.append("memory_space = ?")
            params.append(memory_space)
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        return clauses, params

    @staticmethod
    def _sort_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            hits,
            key=lambda item: (
                str(item.get("occurred_at") or ""),
                SQLiteMemoryStore._safe_float(item.get("score"), 0.0),
            ),
            reverse=True,
        )

    def write_items(self, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        accepted: List[Dict[str, Any]] = []
        rejected_count = 0
        now_iso = self._utc_now_iso()
        with self._connect() as connection:
            for raw_item in items:
                item = raw_item if isinstance(raw_item, dict) else {}
                content = str(item.get("content") or "").strip()
                if not content:
                    rejected_count += 1
                    continue
                user_id, memory_space, _ = self._normalize_scope(
                    item.get("user_id"),
                    item.get("memory_space"),
                    item.get("source_id"),
                )
                entry_id = str(item.get("id") or uuid4())
                source_id = str(item.get("source_id") or item.get("message_id") or entry_id).strip() or entry_id
                occurred_at, ts = self._normalize_occurred_at(item.get("occurred_at"))
                event = {
                    "id": entry_id,
                    "user_id": user_id,
                    "memory_space": memory_space,
                    "source_id": source_id,
                    "ts": ts,
                    "occurred_at": occurred_at,
                    "event_id": str(item.get("event_id") or source_id).strip() or source_id,
                    "event_type": str(item.get("event_type") or "memory_entry").strip() or "memory_entry",
                    "source_platform": str(item.get("source_platform") or "api").strip() or "api",
                    "source_account": str(item.get("source_account") or "").strip(),
                    "message_id": str(item.get("message_id") or source_id).strip(),
                    "sender": str(item.get("sender") or "").strip(),
                    "role": str(item.get("role") or "").strip(),
                    "msg_type": str(item.get("msg_type") or "text").strip() or "text",
                    "content": content,
                    "source_type": str(item.get("source") or item.get("source_type") or "api").strip() or "api",
                    "answer_kind": str(item.get("answer_kind") or "memory_entry").strip() or "memory_entry",
                    "is_question": 1 if bool(item.get("is_question")) else 0,
                    "is_correction": 1 if bool(item.get("is_correction")) else 0,
                    "is_noise": 1 if bool(item.get("is_noise")) else 0,
                    "info_weight": round(max(0.0, min(1.0, self._safe_float(item.get("info_weight"), 0.8))), 4),
                    "trace_ref": str(item.get("trace_ref") or "").strip(),
                    "extra_json": self._json_text(item.get("extra") or item.get("extra_json") or {}),
                    "created_at": now_iso,
                }
                connection.execute(
                    "INSERT INTO timeline_events ("
                    "id, user_id, memory_space, source_id, ts, occurred_at, event_id, event_type, source_platform, source_account, "
                    "message_id, sender, role, msg_type, content, source_type, answer_kind, is_question, is_correction, is_noise, "
                    "info_weight, trace_ref, extra_json, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event["id"],
                        event["user_id"],
                        event["memory_space"],
                        event["source_id"],
                        event["ts"],
                        event["occurred_at"],
                        event["event_id"],
                        event["event_type"],
                        event["source_platform"],
                        event["source_account"],
                        event["message_id"],
                        event["sender"],
                        event["role"],
                        event["msg_type"],
                        event["content"],
                        event["source_type"],
                        event["answer_kind"],
                        event["is_question"],
                        event["is_correction"],
                        event["is_noise"],
                        event["info_weight"],
                        event["trace_ref"],
                        event["extra_json"],
                        event["created_at"],
                    ),
                )
                accepted.append(
                    {
                        "id": event["id"],
                        "user_id": event["user_id"],
                        "memory_space": event["memory_space"],
                        "source_id": event["source_id"],
                        "content": event["content"],
                        "occurred_at": event["occurred_at"],
                        "source": event["source_type"],
                    }
                )
            connection.commit()
        return {
            "status": "ok",
            "memory_ids": [item["id"] for item in accepted],
            "accepted_count": len(accepted),
            "rejected_count": rejected_count,
            "failure_reason": "" if not rejected_count else "some_items_missing_content",
            "items": accepted,
        }

    def save_episode(
        self,
        content: str,
        *,
        category: str = "general",
        source: str = "compact",
        extra: Dict[str, Any] = None,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        occurred_at: Any = None,
    ) -> str:
        body = str(content or "").strip()
        if not body:
            return ""
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        episode_id = str(uuid4())
        occurred_at_iso, ts = self._normalize_occurred_at(occurred_at)
        created_at = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO episodes (id, user_id, memory_space, source_id, ts, occurred_at, category, content, source, extra_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    episode_id,
                    normalized_user_id,
                    normalized_space,
                    normalized_source_id,
                    ts,
                    occurred_at_iso,
                    str(category or "general").strip() or "general",
                    body,
                    str(source or "compact").strip() or "compact",
                    self._json_text(extra or {}),
                    created_at,
                ),
            )
            connection.commit()
        return episode_id

    def save_distillation_material(
        self,
        source_type: str,
        content: str,
        *,
        title: str = "",
        source_ref: str = "",
        weight: float = 1.0,
        quality: float = 1.0,
        used_in_version: str = "",
        status: str = "active",
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        occurred_at: Any = None,
    ) -> str:
        normalized_source_type = str(source_type or "").strip().lower()
        body = str(content or "").strip()
        if not normalized_source_type or not body:
            return ""
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        material_id = str(uuid4())
        occurred_at_iso, ts = self._normalize_occurred_at(occurred_at)
        created_at = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO distillation_materials (id, user_id, memory_space, source_id, ts, occurred_at, source_type, title, content, source_ref, weight, quality, used_in_version, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    material_id,
                    normalized_user_id,
                    normalized_space,
                    normalized_source_id,
                    ts,
                    occurred_at_iso,
                    normalized_source_type,
                    str(title or "").strip(),
                    body,
                    str(source_ref or "").strip(),
                    round(max(0.0, self._safe_float(weight, 1.0)), 4),
                    round(max(0.0, self._safe_float(quality, 1.0)), 4),
                    str(used_in_version or "").strip(),
                    str(status or "active").strip().lower() or "active",
                    created_at,
                ),
            )
            connection.commit()
        return material_id

    def _search_timeline_events(
        self,
        *,
        query: str,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        normalized_query = str(query or "").strip()
        sql = "SELECT * FROM timeline_events"
        if normalized_query:
            clauses.append("content LIKE ?")
            params.append(f"%{normalized_query}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _search_bio_facts(
        self,
        *,
        query: str,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("status = 'active'")
        clauses.append("content LIKE ?")
        params.append(f"%{normalized_query}%")
        sql = "SELECT * FROM bio_facts WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _search_episode_rows(
        self,
        *,
        query: str,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("(content LIKE ? OR category LIKE ?)")
        params.extend([f"%{normalized_query}%", f"%{normalized_query}%"])
        sql = "SELECT * FROM episodes WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _search_distillation_material_rows(
        self,
        *,
        query: str,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("status = 'active'")
        clauses.append("(content LIKE ? OR title LIKE ? OR source_type LIKE ?)")
        params.extend([f"%{normalized_query}%", f"%{normalized_query}%", f"%{normalized_query}%"])
        sql = "SELECT * FROM distillation_materials WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _list_bio_facts_rows(
        self,
        *,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("status = 'active'")
        sql = "SELECT * FROM bio_facts WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _list_episode_rows(
        self,
        *,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
        since_ts: Any = None,
        until_ts: Any = None,
        category: str = "",
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        if since_ts is not None:
            clauses.append("ts >= ?")
            params.append(self._safe_int(since_ts, 0))
        if until_ts is not None:
            clauses.append("ts <= ?")
            params.append(self._safe_int(until_ts, 0))
        normalized_category = str(category or "").strip()
        if normalized_category:
            clauses.append("category = ?")
            params.append(normalized_category)
        sql = "SELECT * FROM episodes"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _list_distillation_material_rows(
        self,
        *,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
        since_ts: Any = None,
        until_ts: Any = None,
        source_type: str = "",
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        normalized_status = str(status or "").strip().lower()
        if normalized_status:
            clauses.append("status = ?")
            params.append(normalized_status)
        if since_ts is not None:
            clauses.append("ts >= ?")
            params.append(self._safe_int(since_ts, 0))
        if until_ts is not None:
            clauses.append("ts <= ?")
            params.append(self._safe_int(until_ts, 0))
        normalized_source_type = str(source_type or "").strip().lower()
        if normalized_source_type:
            clauses.append("source_type = ?")
            params.append(normalized_source_type)
        sql = "SELECT * FROM distillation_materials"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _search_fact_slots_rows(
        self,
        *,
        query: str,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("status = 'active'")
        clauses.append("(topic LIKE ? OR fact_key LIKE ? OR value_text LIKE ?)")
        params.extend([f"%{normalized_query}%", f"%{normalized_query}%", f"%{normalized_query}%"])
        sql = "SELECT * FROM fact_slots WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _list_fact_slots_rows(
        self,
        *,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("status = 'active'")
        sql = "SELECT * FROM fact_slots WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search(
        self,
        *,
        query: str,
        limit: int = 20,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        capped_limit = max(1, min(self._safe_int(limit, 20), 100))
        timeline_rows = self._search_timeline_events(
            query=query,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        fact_rows = self._search_bio_facts(
            query=query,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        episode_rows = self._search_episode_rows(
            query=query,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        material_rows = self._search_distillation_material_rows(
            query=query,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        fact_slot_rows = self._search_fact_slots_rows(
            query=query,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        hits: List[Dict[str, Any]] = []
        for row in timeline_rows:
            hits.append(build_search_hit(row, score=1.0, source_kind=str(row.get("event_type") or "timeline_event")))
        for row in episode_rows:
            hits.append(build_search_hit(row, score=0.97, source_kind="timeline_episode"))
        for row in material_rows:
            hits.append(build_search_hit(row, score=0.95, source_kind="timeline_material"))
        for row in fact_rows:
            hits.append(build_search_hit(row, score=0.92, source_kind="bio_fact"))
        for row in fact_slot_rows:
            hits.append(build_search_hit(row, score=0.9, source_kind="fact_slot"))
        hits = self._sort_hits(hits)
        raw_count = len(hits)
        truncated = raw_count > capped_limit
        return {
            "status": "ok",
            "query": str(query or "").strip(),
            "user_id": normalized_user_id,
            "memory_space": normalized_space,
            "source_id": normalized_source_id,
            "hits": hits[:capped_limit],
            "raw_count": raw_count,
            "truncated": truncated,
        }

    @staticmethod
    def _parse_timezone(timezone_name: str) -> timezone:
        raw = str(timezone_name or "UTC").strip()
        if not raw or raw.upper() == "UTC":
            return timezone.utc
        if len(raw) == 6 and raw[0] in {"+", "-"} and raw[3] == ":":
            sign = 1 if raw[0] == "+" else -1
            hours = int(raw[1:3])
            minutes = int(raw[4:6])
            delta = timedelta(hours=hours, minutes=minutes)
            return timezone(sign * delta)
        raise ValueError("invalid timezone")

    def _timeline_hits_between(
        self,
        *,
        start_dt: datetime,
        end_dt: datetime,
        limit: int,
        user_id: str,
        memory_space: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        clauses, params = self._build_scope_clauses(
            user_id=user_id,
            memory_space=memory_space,
            source_id=source_id,
        )
        clauses.append("ts >= ?")
        params.append(int(start_dt.timestamp()))
        clauses.append("ts < ?")
        params.append(int(end_dt.timestamp()))
        sql = "SELECT * FROM timeline_events WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_timeline_events(
        self,
        *,
        limit: int = 100,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        since_ts: Any = None,
        until_ts: Any = None,
        event_type: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        clauses, params = self._build_scope_clauses(
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            user_required=True,
        )
        if since_ts is not None:
            clauses.append("ts >= ?")
            params.append(self._safe_int(since_ts, 0))
        if until_ts is not None:
            clauses.append("ts <= ?")
            params.append(self._safe_int(until_ts, 0))
        normalized_event_type = str(event_type or "").strip().lower()
        if normalized_event_type:
            clauses.append("event_type = ?")
            params.append(normalized_event_type)
        sql = "SELECT * FROM timeline_events WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, self._safe_int(limit, 100)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search_timeline_events(
        self,
        query: str,
        *,
        limit: int = 20,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> List[Dict[str, Any]]:
        return self._search_timeline_events(
            query=query,
            limit=max(1, self._safe_int(limit, 20)),
            user_id=self._normalize_scope(user_id, memory_space, source_id)[0],
            memory_space=self._normalize_scope(user_id, memory_space, source_id)[1],
            source_id=self._normalize_scope(user_id, memory_space, source_id)[2],
        )

    def search_facts(
        self,
        query: str,
        *,
        limit: int = 10,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        normalized_query = str(query or "").strip()
        capped_limit = max(1, self._safe_int(limit, 10))
        if not normalized_query:
            clauses, params = self._build_scope_clauses(
                user_id=normalized_user_id,
                memory_space=normalized_space,
                source_id=normalized_source_id,
                user_required=True,
            )
            clauses.append("status = 'active'")
            sql = "SELECT * FROM bio_facts WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
            params.append(capped_limit)
            with self._connect() as connection:
                rows = connection.execute(sql, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
        return self._search_bio_facts(
            query=normalized_query,
            limit=capped_limit,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )

    def list_episodes(
        self,
        *,
        limit: int = 100,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        since_ts: Any = None,
        until_ts: Any = None,
        category: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        return self._list_episode_rows(
            limit=max(1, self._safe_int(limit, 100)),
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            since_ts=since_ts,
            until_ts=until_ts,
            category=category,
        )

    def search_episodes(
        self,
        query: str,
        *,
        limit: int = 10,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return self._list_episode_rows(
                limit=max(1, self._safe_int(limit, 10)),
                user_id=normalized_user_id,
                memory_space=normalized_space,
                source_id=normalized_source_id,
            )
        return self._search_episode_rows(
            query=normalized_query,
            limit=max(1, self._safe_int(limit, 10)),
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )

    def list_distillation_materials(
        self,
        *,
        limit: int = 100,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        since_ts: Any = None,
        until_ts: Any = None,
        source_type: str = "",
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        return self._list_distillation_material_rows(
            limit=max(1, self._safe_int(limit, 100)),
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            since_ts=since_ts,
            until_ts=until_ts,
            source_type=source_type,
            status=status,
        )

    def search_distillation_materials(
        self,
        query: str,
        *,
        limit: int = 10,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return self._list_distillation_material_rows(
                limit=max(1, self._safe_int(limit, 10)),
                user_id=normalized_user_id,
                memory_space=normalized_space,
                source_id=normalized_source_id,
            )
        return self._search_distillation_material_rows(
            query=normalized_query,
            limit=max(1, self._safe_int(limit, 10)),
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )

    def search_fact_slots(
        self,
        query: str,
        *,
        limit: int = 8,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> List[Dict[str, Any]]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        return self._search_fact_slots_rows(
            query=str(query or "").strip(),
            limit=max(1, self._safe_int(limit, 8)),
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )

    def get_fact_slot(
        self,
        topic: str,
        fact_key: str,
        *,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        normalized_topic = str(topic or "").strip()
        normalized_fact_key = str(fact_key or "").strip()
        if not normalized_topic or not normalized_fact_key:
            return {}
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        clauses, params = self._build_scope_clauses(
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            user_required=True,
        )
        clauses.extend(["topic = ?", "fact_key = ?", "status = 'active'"])
        params.extend([normalized_topic, normalized_fact_key])
        sql = "SELECT * FROM fact_slots WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return self._row_to_dict(row) if row else {}

    def list_fact_slot_versions(
        self,
        topic: str,
        fact_key: str,
        *,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        status: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        normalized_topic = str(topic or "").strip()
        normalized_fact_key = str(fact_key or "").strip()
        if not normalized_topic or not normalized_fact_key:
            return []
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        clauses, params = self._build_scope_clauses(
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            user_required=True,
        )
        clauses.extend(["topic = ?", "fact_key = ?"])
        params.extend([normalized_topic, normalized_fact_key])
        normalized_status = str(status or "").strip().lower()
        if normalized_status:
            clauses.append("status = ?")
            params.append(normalized_status)
        params.append(max(1, min(100, self._safe_int(limit, 20))))
        sql = "SELECT * FROM fact_slots WHERE " + " AND ".join(clauses) + " ORDER BY ts DESC LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def has_recent_fact_slot_update(
        self,
        cutoff_ts: int,
        *,
        topic_prefix: str = "",
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> bool:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        clauses, params = self._build_scope_clauses(
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            user_required=True,
        )
        clauses.extend(["status = 'active'", "ts >= ?"])
        params.append(self._safe_int(cutoff_ts, 0))
        normalized_prefix = str(topic_prefix or "").strip()
        if normalized_prefix:
            clauses.append("topic LIKE ?")
            params.append(f"{normalized_prefix}%")
        sql = "SELECT 1 FROM fact_slots WHERE " + " AND ".join(clauses) + " LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return bool(row)

    def upsert_fact_slot(
        self,
        *,
        topic: str,
        fact_key: str,
        value_text: str,
        value_type: str = "text",
        normalized_value: str = "",
        source_fact_id: str = "",
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        confidence: float = 1.0,
        status: str = "active",
        occurred_at: Any = None,
    ) -> str:
        normalized_topic = str(topic or "").strip()
        normalized_fact_key = str(fact_key or "").strip()
        normalized_value_text = str(value_text or "").strip()
        if not normalized_topic or not normalized_fact_key or not normalized_value_text:
            return ""
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        slot_id = str(uuid4())
        normalized_source_fact_id = str(source_fact_id or "").strip()
        occurred_at_iso, ts = self._normalize_occurred_at(occurred_at)
        created_at = self._utc_now_iso()
        with self._connect() as connection:
            normalized_status = str(status or "active").strip().lower() or "active"
            if normalized_status == "active":
                incoming_rank = None
                if normalized_source_fact_id:
                    try:
                        incoming_rank = int(normalized_source_fact_id)
                    except Exception:
                        incoming_rank = None
                if incoming_rank is not None:
                    current_row = connection.execute(
                        "SELECT id, source_fact_id FROM fact_slots WHERE user_id=? AND memory_space=? AND topic=? AND fact_key=? AND status='active' ORDER BY ts DESC LIMIT 1",
                        (
                            normalized_user_id,
                            normalized_space,
                            normalized_topic,
                            normalized_fact_key,
                        ),
                    ).fetchone()
                    if current_row is not None:
                        current_source_fact_id = str(current_row["source_fact_id"] or "").strip()
                        try:
                            current_rank = int(current_source_fact_id)
                        except Exception:
                            current_rank = None
                        if current_rank is not None and current_rank > incoming_rank:
                            return str(current_row["id"] or "")
                connection.execute(
                    "UPDATE fact_slots SET status='superseded' WHERE user_id=? AND memory_space=? AND topic=? AND fact_key=? AND status='active'",
                    (
                        normalized_user_id,
                        normalized_space,
                        normalized_topic,
                        normalized_fact_key,
                    ),
                )
            connection.execute(
                "INSERT INTO fact_slots ("
                "id, user_id, memory_space, source_id, ts, occurred_at, topic, fact_key, value_text, value_type, normalized_value, source_fact_id, confidence, status, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    slot_id,
                    normalized_user_id,
                    normalized_space,
                    normalized_source_id,
                    ts,
                    occurred_at_iso,
                    normalized_topic,
                    normalized_fact_key,
                    normalized_value_text,
                    str(value_type or "text").strip() or "text",
                    str(normalized_value or "").strip(),
                    normalized_source_fact_id,
                    round(max(0.0, min(1.0, self._safe_float(confidence, 1.0))), 4),
                    normalized_status,
                    created_at,
                ),
            )
            connection.commit()
        return slot_id

    def save_event_reference(
        self,
        *,
        source_event_id: str,
        target_event_id: str,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        reference_type: str = "timeline_quote",
        reason: str = "",
        score: float = 0.0,
        extra: Dict[str, Any] = None,
        occurred_at: Any = None,
    ) -> str:
        src = str(source_event_id or "").strip()
        tgt = str(target_event_id or "").strip()
        if not src or not tgt:
            return ""
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        reference_id = str(uuid4())
        occurred_at_iso, ts = self._normalize_occurred_at(occurred_at)
        created_at = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO event_references ("
                "id, user_id, memory_space, source_id, ts, occurred_at, source_event_id, target_event_id, reference_type, reason, score, extra_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reference_id,
                    normalized_user_id,
                    normalized_space,
                    normalized_source_id,
                    ts,
                    occurred_at_iso,
                    src,
                    tgt,
                    str(reference_type or "timeline_quote").strip().lower() or "timeline_quote",
                    str(reason or "").strip(),
                    round(max(0.0, min(1.0, self._safe_float(score, 0.0))), 4),
                    self._json_text(extra or {}),
                    created_at,
                ),
            )
            connection.commit()
        return reference_id

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
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        tz = self._parse_timezone(timezone_name)
        try:
            target = datetime.strptime(str(day or "").strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("invalid date") from exc
        local_start = datetime.combine(target, time.min, tzinfo=tz)
        local_end = local_start + timedelta(days=1)
        utc_start = local_start.astimezone(timezone.utc)
        utc_end = local_end.astimezone(timezone.utc)
        capped_limit = max(1, min(self._safe_int(limit, 50), 100))
        rows = self._timeline_hits_between(
            start_dt=utc_start,
            end_dt=utc_end,
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        episode_rows = self._list_episode_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            since_ts=int(utc_start.timestamp()),
            until_ts=int(utc_end.timestamp()) - 1,
        )
        material_rows = self._list_distillation_material_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            since_ts=int(utc_start.timestamp()),
            until_ts=int(utc_end.timestamp()) - 1,
            status="active",
        )
        hits = [
            build_search_hit(row, score=1.0, source_kind=str(row.get("event_type") or "timeline_event"))
            for row in rows
        ]
        hits.extend(build_search_hit(row, score=0.97, source_kind="timeline_episode") for row in episode_rows)
        hits.extend(build_search_hit(row, score=0.95, source_kind="timeline_material") for row in material_rows)
        hits = self._sort_hits(hits)
        truncated = len(hits) > capped_limit
        return build_recall_result(
            hits=hits[:capped_limit],
            day=target.isoformat(),
            timezone_name=str(timezone_name or "UTC"),
            mode="date_recall",
            truncated=truncated,
        )

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
        return result

    def delete_by_ids(
        self,
        ids: Iterable[str],
        *,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        normalized_ids = []
        for item in ids:
            text = str(item or "").strip()
            if text and text not in normalized_ids:
                normalized_ids.append(text)
        if not normalized_ids:
            return {"status": "ok", "deleted_count": 0, "not_found_count": 0, "failure_reason": ""}
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        placeholders = ", ".join("?" for _ in normalized_ids)
        clauses, params = self._build_scope_clauses(
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            user_required=True,
        )
        where_sql = "id IN (" + placeholders + ")"
        if clauses:
            where_sql += " AND " + " AND ".join(clauses)
        with self._connect() as connection:
            existing_rows = connection.execute(
                "SELECT id FROM timeline_events WHERE " + where_sql,
                (*normalized_ids, *params),
            ).fetchall()
            episode_rows = connection.execute(
                "SELECT id FROM episodes WHERE " + where_sql,
                (*normalized_ids, *params),
            ).fetchall()
            fact_rows = connection.execute(
                "SELECT id FROM bio_facts WHERE " + where_sql,
                (*normalized_ids, *params),
            ).fetchall()
            slot_rows = connection.execute(
                "SELECT id FROM fact_slots WHERE " + where_sql,
                (*normalized_ids, *params),
            ).fetchall()
            material_rows = connection.execute(
                "SELECT id FROM distillation_materials WHERE " + where_sql,
                (*normalized_ids, *params),
            ).fetchall()
            existing_ids = {str(row[0]) for row in existing_rows}
            existing_ids.update(str(row[0]) for row in episode_rows)
            existing_ids.update(str(row[0]) for row in fact_rows)
            existing_ids.update(str(row[0]) for row in slot_rows)
            existing_ids.update(str(row[0]) for row in material_rows)
            connection.execute(
                "DELETE FROM timeline_events WHERE " + where_sql,
                (*normalized_ids, *params),
            )
            connection.execute(
                "DELETE FROM episodes WHERE " + where_sql,
                (*normalized_ids, *params),
            )
            connection.execute(
                "DELETE FROM bio_facts WHERE " + where_sql,
                (*normalized_ids, *params),
            )
            connection.execute(
                "DELETE FROM fact_slots WHERE " + where_sql,
                (*normalized_ids, *params),
            )
            connection.execute(
                "DELETE FROM distillation_materials WHERE " + where_sql,
                (*normalized_ids, *params),
            )
            connection.commit()
        deleted_count = len(existing_ids)
        return {
            "status": "ok",
            "deleted_count": deleted_count,
            "not_found_count": max(0, len(normalized_ids) - deleted_count),
            "failure_reason": "",
        }

    def export_entries(
        self,
        *,
        user_id: str = "",
        memory_space: str = "",
        source_id: str = "",
        limit: int = 500,
        export_format: str = "json",
    ) -> Dict[str, Any]:
        normalized_user_id, normalized_space, normalized_source_id = self._normalize_scope(
            user_id,
            memory_space,
            source_id,
        )
        capped_limit = max(1, min(self._safe_int(limit, 500), 1000))
        rows = self._search_timeline_events(
            query="",
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        episode_rows = self._list_episode_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        fact_rows = self._list_bio_facts_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        fact_slot_rows = self._list_fact_slots_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
        )
        material_rows = self._list_distillation_material_rows(
            limit=capped_limit + 1,
            user_id=normalized_user_id,
            memory_space=normalized_space,
            source_id=normalized_source_id,
            status="active",
        )
        items = [build_export_item(row, source_kind=str(row.get("event_type") or "timeline_event")) for row in rows]
        items.extend(build_export_item(row, source_kind="timeline_episode") for row in episode_rows)
        items.extend(build_export_item(row, source_kind="bio_fact") for row in fact_rows)
        items.extend(build_export_item(row, source_kind="fact_slot") for row in fact_slot_rows)
        items.extend(build_export_item(row, source_kind="timeline_material") for row in material_rows)
        items = self._sort_hits(items)
        truncated = len(items) > capped_limit
        return {
            "status": "ok",
            "export_id": str(uuid4()),
            "format": str(export_format or "json").strip() or "json",
            "count": len(items[:capped_limit]),
            "truncated": truncated,
            "filters": {
                "user_id": normalized_user_id,
                "memory_space": normalized_space,
                "source_id": normalized_source_id,
            },
            "items": items[:capped_limit],
        }
