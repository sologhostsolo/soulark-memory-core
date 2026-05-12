import tempfile
import unittest

from memory_core.app import create_app
from memory_core.config import Settings


class MemoryCoreSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        app = create_app(Settings(database_path=db_path))
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_memory_core_minimal_closed_loop(self):
        write_response = self.client.post(
            "/api/v1/write",
            json={
                "items": [
                    {
                        "user_id": "demo-user",
                        "content": "今天开始搭 Memory Core 最小骨架。",
                        "source": "smoke-test",
                        "occurred_at": "2026-05-12T10:00:00+00:00",
                    }
                ]
            },
        )
        self.assertEqual(200, write_response.status_code)
        write_payload = write_response.get_json()
        self.assertEqual(1, write_payload["accepted_count"])
        memory_id = write_payload["memory_ids"][0]

        search_response = self.client.post(
            "/api/v1/search",
            json={"query": "Memory Core", "user_id": "demo-user", "limit": 5},
        )
        self.assertEqual(200, search_response.status_code)
        search_payload = search_response.get_json()
        self.assertEqual(1, search_payload["raw_count"])
        self.assertEqual(memory_id, search_payload["hits"][0]["id"])

        date_response = self.client.post(
            "/api/v1/date-recall",
            json={"date": "2026-05-12", "user_id": "demo-user"},
        )
        self.assertEqual(200, date_response.status_code)
        self.assertEqual(1, date_response.get_json()["hit_count"])

        daily_response = self.client.post(
            "/api/v1/daily-recall",
            json={"date": "2026-05-12", "user_id": "demo-user"},
        )
        self.assertEqual(200, daily_response.status_code)
        self.assertEqual("daily_recall", daily_response.get_json()["mode"])

        export_response = self.client.get("/api/v1/export?user_id=demo-user")
        self.assertEqual(200, export_response.status_code)
        self.assertEqual(1, export_response.get_json()["count"])

        delete_response = self.client.post(
            "/api/v1/delete",
            json={"ids": [memory_id], "user_id": "demo-user"},
        )
        self.assertEqual(200, delete_response.status_code)
        self.assertEqual(1, delete_response.get_json()["deleted_count"])

        empty_search = self.client.post(
            "/api/v1/search",
            json={"query": "Memory Core", "user_id": "demo-user", "limit": 5},
        )
        self.assertEqual(0, empty_search.get_json()["raw_count"])


if __name__ == "__main__":
    unittest.main()