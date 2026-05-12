import json
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MemoryCoreHttpClient:
    def __init__(self, base_url: str):
        self.base_url = str(base_url or "http://127.0.0.1:8765").rstrip("/")

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = Request(
            url=self.base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = self.base_url + path + ("?" + query if query else "")
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def write_memory(self, *, user_id: str, memory_space: str, source_id: str, content: str, occurred_at: str) -> Dict[str, Any]:
        return self._post(
            "/api/v1/write",
            {
                "items": [
                    {
                        "user_id": user_id,
                        "memory_space": memory_space,
                        "source_id": source_id,
                        "content": content,
                        "source": "personal-sample",
                        "event_type": "raw_message",
                        "sender": "user",
                        "occurred_at": occurred_at,
                    }
                ]
            },
        )

    def search(self, *, query: str, user_id: str, memory_space: str, limit: int = 5) -> Dict[str, Any]:
        return self._post(
            "/api/v1/search",
            {"query": query, "user_id": user_id, "memory_space": memory_space, "limit": limit},
        )

    def daily_recall(self, *, day: str, user_id: str, memory_space: str, timezone: str = "UTC") -> Dict[str, Any]:
        return self._post(
            "/api/v1/daily-recall",
            {"date": day, "user_id": user_id, "memory_space": memory_space, "timezone": timezone},
        )

    def export(self, *, user_id: str, memory_space: str, export_format: str = "json") -> Dict[str, Any]:
        return self._get(
            "/api/v1/export",
            {"user_id": user_id, "memory_space": memory_space, "format": export_format},
        )


def run_personal_integration_sample(base_url: str = "http://127.0.0.1:8765") -> Dict[str, Any]:
    client = MemoryCoreHttpClient(base_url)
    write_result = client.write_memory(
        user_id="demo-user",
        memory_space="personal",
        source_id="personal-sample-001",
        content="Personal 侧通过 Core 记录一条 Day 10 集成样例。",
        occurred_at="2026-05-12T18:00:00+00:00",
    )
    search_result = client.search(
        query="Day 10 集成样例",
        user_id="demo-user",
        memory_space="personal",
        limit=5,
    )
    daily_result = client.daily_recall(
        day="2026-05-12",
        user_id="demo-user",
        memory_space="personal",
        timezone="UTC",
    )
    export_result = client.export(
        user_id="demo-user",
        memory_space="personal",
        export_format="json",
    )
    return {
        "write": write_result,
        "search": search_result,
        "daily_recall": daily_result,
        "export": export_result,
    }


if __name__ == "__main__":
    print(json.dumps(run_personal_integration_sample(), ensure_ascii=False, indent=2))