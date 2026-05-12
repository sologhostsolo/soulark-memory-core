import json
from typing import Any, Dict

from flask import Flask, jsonify, request

from memory_core.config import Settings
from memory_core.executor import MemoryCoreExecutor
from memory_core.store import SQLiteMemoryStore


def _payload() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def _json_error(*, message: str, error_code: str, status_code: int = 400):
    return jsonify({"status": "error", "error_code": error_code, "message": message}), status_code


def create_app(settings: Settings = None) -> Flask:
    effective_settings = settings or Settings.from_env()
    app = Flask(__name__)
    store = SQLiteMemoryStore(effective_settings.database_path)
    store.initialize()
    executor = MemoryCoreExecutor(store)

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "soulark-memory-core",
                "version": "0.1.0-dev",
                "scope": ["write", "search", "date_recall", "daily_recall", "delete", "export"],
                "docs": "/demo",
            }
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "database_path": effective_settings.database_path})

    @app.get("/demo")
    def demo():
        body = {
            "service": "SoulArk Memory Core",
            "quick_start": [
                "POST /api/v1/write",
                "POST /api/v1/search",
                "POST /api/v1/date-recall",
                "POST /api/v1/daily-recall",
                "POST /api/v1/delete",
                "GET /api/v1/export",
            ],
            "example_write": {
                "items": [
                    {
                        "user_id": "demo-user",
                        "content": "今天确认先把 Memory Core 范围写死。",
                        "source": "demo",
                        "occurred_at": "2026-05-12T09:00:00+00:00",
                    }
                ]
            },
        }
        return (
            "<html><body><h1>SoulArk Memory Core</h1><pre>"
            + json.dumps(body, ensure_ascii=False, indent=2)
            + "</pre></body></html>"
        )

    @app.post("/api/v1/write")
    def write():
        data = _payload()
        items = data.get("items")
        if isinstance(items, list):
            payload_items = items
        else:
            payload_items = [data] if data else []
        if not payload_items:
            return _json_error(message="write requires items", error_code="invalid_write_request")
        result = store.write_items(payload_items)
        return jsonify(result)

    @app.post("/api/v1/search")
    def search():
        data = _payload()
        result = executor.search(
            query=str(data.get("query") or ""),
            limit=_safe_int(data.get("limit"), 20, 1, 100),
            user_id=str(data.get("user_id") or ""),
            memory_space=str(data.get("memory_space") or ""),
            source_id=str(data.get("source_id") or ""),
        )
        return jsonify(result)

    @app.post("/api/v1/date-recall")
    def date_recall():
        data = _payload()
        try:
            result = executor.date_recall(
                day=str(data.get("date") or ""),
                limit=_safe_int(data.get("limit"), 50, 1, 100),
                user_id=str(data.get("user_id") or ""),
                memory_space=str(data.get("memory_space") or ""),
                source_id=str(data.get("source_id") or ""),
                timezone_name=str(data.get("timezone") or "UTC"),
            )
        except ValueError as exc:
            return _json_error(message=str(exc), error_code="invalid_date_recall_request")
        return jsonify(result)

    @app.post("/api/v1/daily-recall")
    def daily_recall():
        data = _payload()
        try:
            result = executor.daily_recall(
                day=str(data.get("date") or ""),
                limit=_safe_int(data.get("limit"), 50, 1, 100),
                user_id=str(data.get("user_id") or ""),
                memory_space=str(data.get("memory_space") or ""),
                source_id=str(data.get("source_id") or ""),
                timezone_name=str(data.get("timezone") or "UTC"),
            )
        except ValueError as exc:
            return _json_error(message=str(exc), error_code="invalid_daily_recall_request")
        return jsonify(result)

    @app.post("/api/v1/delete")
    def delete():
        data = _payload()
        result = store.delete_by_ids(
            ids=data.get("ids") if isinstance(data.get("ids"), list) else [],
            user_id=str(data.get("user_id") or ""),
            memory_space=str(data.get("memory_space") or ""),
            source_id=str(data.get("source_id") or ""),
        )
        return jsonify(result)

    @app.get("/api/v1/export")
    def export_entries():
        result = store.export_entries(
            user_id=str(request.args.get("user_id") or ""),
            memory_space=str(request.args.get("memory_space") or ""),
            source_id=str(request.args.get("source_id") or ""),
            limit=_safe_int(request.args.get("limit"), 500, 1, 1000),
            export_format=str(request.args.get("format") or "json"),
        )
        return jsonify(result)

    return app