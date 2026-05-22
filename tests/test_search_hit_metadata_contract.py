import tempfile
import unittest

from memory_core.app import create_app
from memory_core.config import Settings


class SearchHitMetadataContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        app = create_app(Settings(database_path=db_path))
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_search_hit_returns_trace_weight_and_extra_json(self):
        write_response = self.client.post(
            "/api/v1/write",
            json={
                "items": [
                    {
                        "user_id": "team-demo",
                        "memory_space": "work",
                        "source_id": "decision-acme-001",
                        "content": "Acme metadata contract verifies Work Memory search hit fields.",
                        "source": "work-memory-contract-test",
                        "event_type": "decision",
                        "answer_kind": "decision",
                        "occurred_at": "2026-05-22T10:00:00+00:00",
                        "trace_ref": "acme-meeting-2026-05-22",
                        "info_weight": 0.93,
                        "extra": {
                            "project_id": "acme-support-memory-pilot",
                            "customer_id": "acme",
                            "work_type": "decision",
                            "status": "active",
                        },
                    }
                ]
            },
        )
        self.assertEqual(200, write_response.status_code)
        self.assertEqual("ok", write_response.get_json()["status"])

        search_payload = self.client.post(
            "/api/v1/search",
            json={
                "query": "Acme metadata contract",
                "user_id": "team-demo",
                "memory_space": "work",
                "limit": 5,
            },
        ).get_json()

        self.assertEqual("ok", search_payload["status"])
        self.assertEqual(1, search_payload["raw_count"])
        hit = search_payload["hits"][0]
        self.assertEqual("acme-meeting-2026-05-22", hit["trace_ref"])
        self.assertEqual(0.93, hit["info_weight"])
        self.assertEqual(
            {
                "project_id": "acme-support-memory-pilot",
                "customer_id": "acme",
                "work_type": "decision",
                "status": "active",
            },
            hit["extra_json"],
        )
