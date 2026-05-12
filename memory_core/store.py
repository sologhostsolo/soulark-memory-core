import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


class SQLiteMemoryStore:
    def __init__(self, database_path: str):
        self.database_path = str(database_path or "data/memory_core.db").strip() or "data/memory_core.db"
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(self.database_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS memory_entries ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "content TEXT NOT NULL, "
                "source TEXT NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_entries_user_time "
                "ON memory_entries (user_id, occurred_at DESC)"
            )
            connection.commit()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @classmethod
    def _normalize_occurred_at(cls, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return cls._utc_now_iso()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            if len(raw) == 10:
                parsed_date = datetime.strptime(raw, "%Y-%m-%d").date()
                return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc).isoformat()
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return cls._utc_now_iso()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "content": row["content"],
            "source": row["source"],
            "occurred_at": row["occurred_at"],
            "created_at": row["created_at"],
        }

    def write_items(self, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        accepted: List[Dict[str, Any]] = []
        rejected_count = 0
        now_iso = self._utc_now_iso()
        with self._connect() as connection:
            for item in items:
                content = str((item or {}).get("content") or "").strip()
                if not content:
                    rejected_count += 1
                    continue
                entry = {
                    "id": str((item or {}).get("id") or uuid4()),
                    "user_id": str((item or {}).get("user_id") or "default").strip() or "default",
                    "content": content,
                    "source": str((item or {}).get("source") or "manual").strip() or "manual",
                    "occurred_at": self._normalize_occurred_at((item or {}).get("occurred_at")),
                    "created_at": now_iso,
                }
                connection.execute(
                    "INSERT INTO memory_entries (id, user_id, content, source, occurred_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry["id"],
                        entry["user_id"],
                        entry["content"],
                        entry["source"],
                        entry["occurred_at"],
                        entry["created_at"],
                    ),
                )
                accepted.append(entry)
            connection.commit()
        return {
            "status": "ok",
            "memory_ids": [item["id"] for item in accepted],
            "accepted_count": len(accepted),
            "rejected_count": rejected_count,
            "items": accepted,
        }

    def search(self, *, query: str, limit: int = 20, user_id: str = "") -> Dict[str, Any]:
        normalized_query = str(query or "").strip()
        normalized_user_id = str(user_id or "").strip()
        capped_limit = max(1, min(int(limit or 20), 100))
        sql = "SELECT * FROM memory_entries"
        params: List[Any] = []
        clauses: List[str] = []
        if normalized_query:
            clauses.append("content LIKE ?")
            params.append(f"%{normalized_query}%")
        if normalized_user_id:
            clauses.append("user_id = ?")
            params.append(normalized_user_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at DESC LIMIT ?"
        params.append(capped_limit + 1)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > capped_limit
        hits = [self._row_to_item(row) for row in rows[:capped_limit]]
        return {"hits": hits, "raw_count": len(hits), "truncated": truncated}

    def date_recall(self, *, day: str, limit: int = 50, user_id: str = "") -> Dict[str, Any]:
        target = datetime.strptime(str(day or "").strip(), "%Y-%m-%d").date()
        start = datetime.combine(target, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        capped_limit = max(1, min(int(limit or 50), 100))
        sql = (
            "SELECT * FROM memory_entries WHERE occurred_at >= ? AND occurred_at < ?"
        )
        params: List[Any] = [start.isoformat(), end.isoformat()]
        normalized_user_id = str(user_id or "").strip()
        if normalized_user_id:
            sql += " AND user_id = ?"
            params.append(normalized_user_id)
        sql += " ORDER BY occurred_at DESC LIMIT ?"
        params.append(capped_limit + 1)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > capped_limit
        hits = [self._row_to_item(row) for row in rows[:capped_limit]]
        return {"date": target.isoformat(), "hits": hits, "hit_count": len(hits), "truncated": truncated}

    def daily_recall(self, *, day: str, limit: int = 50, user_id: str = "") -> Dict[str, Any]:
        payload = self.date_recall(day=day, limit=limit, user_id=user_id)
        payload["mode"] = "daily_recall"
        return payload

    def delete_by_ids(self, ids: Iterable[str], *, user_id: str = "") -> Dict[str, Any]:
        normalized_ids = [str(item or "").strip() for item in ids if str(item or "").strip()]
        if not normalized_ids:
            return {"status": "ok", "deleted_count": 0}
        placeholders = ", ".join("?" for _ in normalized_ids)
        sql = f"DELETE FROM memory_entries WHERE id IN ({placeholders})"
        params: List[Any] = list(normalized_ids)
        normalized_user_id = str(user_id or "").strip()
        if normalized_user_id:
            sql += " AND user_id = ?"
            params.append(normalized_user_id)
        with self._connect() as connection:
            cursor = connection.execute(sql, params)
            connection.commit()
        return {"status": "ok", "deleted_count": int(cursor.rowcount or 0)}

    def export_entries(self, *, user_id: str = "", limit: int = 500) -> Dict[str, Any]:
        capped_limit = max(1, min(int(limit or 500), 1000))
        sql = "SELECT * FROM memory_entries"
        params: List[Any] = []
        normalized_user_id = str(user_id or "").strip()
        if normalized_user_id:
            sql += " WHERE user_id = ?"
            params.append(normalized_user_id)
        sql += " ORDER BY occurred_at DESC LIMIT ?"
        params.append(capped_limit + 1)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > capped_limit
        items = [self._row_to_item(row) for row in rows[:capped_limit]]
        return {"items": items, "count": len(items), "truncated": truncated}