import json
import socket
import tempfile
import threading
import unittest

from examples.personal_core_integration_sample import run_personal_integration_sample
from memory_core.app import create_app
from memory_core.config import Settings
from memory_core.executor import MemoryCoreExecutor
from memory_core.normalizer import normalize_memory_evidence
from memory_core.store import SQLiteMemoryStore
from werkzeug.serving import make_server


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
                        "memory_space": "personal",
                        "source_id": "msg-001",
                        "content": "今天开始搭 Memory Core 最小骨架。",
                        "source": "smoke-test",
                        "event_type": "raw_message",
                        "sender": "user",
                        "occurred_at": "2026-05-12T10:00:00+00:00",
                    }
                ]
            },
        )
        self.assertEqual(200, write_response.status_code)
        write_payload = write_response.get_json()
        self.assertEqual("ok", write_payload["status"])
        self.assertEqual(1, write_payload["accepted_count"])
        memory_id = write_payload["memory_ids"][0]
        self.assertEqual("personal", write_payload["items"][0]["memory_space"])
        self.assertEqual("msg-001", write_payload["items"][0]["source_id"])

        search_response = self.client.post(
            "/api/v1/search",
            json={"query": "Memory Core", "user_id": "demo-user", "memory_space": "personal", "limit": 5},
        )
        self.assertEqual(200, search_response.status_code)
        search_payload = search_response.get_json()
        self.assertEqual("ok", search_payload["status"])
        self.assertEqual(1, search_payload["raw_count"])
        self.assertEqual(memory_id, search_payload["hits"][0]["id"])
        self.assertEqual("personal", search_payload["hits"][0]["memory_space"])
        self.assertEqual("msg-001", search_payload["hits"][0]["source_id"])
        self.assertIn("score", search_payload["hits"][0])
        self.assertTrue(search_payload["hits"][0]["evidence"])

        date_response = self.client.post(
            "/api/v1/date-recall",
            json={"date": "2026-05-12", "user_id": "demo-user", "memory_space": "personal", "timezone": "UTC"},
        )
        self.assertEqual(200, date_response.status_code)
        date_payload = date_response.get_json()
        self.assertEqual(1, date_payload["hit_count"])
        self.assertEqual("date_recall", date_payload["mode"])
        self.assertEqual("UTC", date_payload["timezone"])
        self.assertTrue(date_payload["evidence"])
        self.assertTrue(date_payload["date_scope"]["enabled"])
        self.assertEqual(["2026-05-12"], date_payload["date_scope"]["target_dates"])

        daily_response = self.client.post(
            "/api/v1/daily-recall",
            json={"date": "2026-05-12", "user_id": "demo-user", "memory_space": "personal", "timezone": "UTC"},
        )
        self.assertEqual(200, daily_response.status_code)
        daily_payload = daily_response.get_json()
        self.assertEqual("daily_recall", daily_payload["mode"])
        self.assertEqual(1, daily_payload["daily_recall"]["entry_count"])
        self.assertEqual(["2026-05-12"], daily_payload["daily_recall"]["target_dates"])
        self.assertTrue(daily_payload["daily_recall"]["grouped"])

        export_response = self.client.get("/api/v1/export?user_id=demo-user&memory_space=personal&format=json")
        self.assertEqual(200, export_response.status_code)
        export_payload = export_response.get_json()
        self.assertEqual(1, export_payload["count"])
        self.assertEqual("json", export_payload["format"])
        self.assertTrue(export_payload["export_id"])

        delete_response = self.client.post(
            "/api/v1/delete",
            json={"ids": [memory_id], "user_id": "demo-user", "memory_space": "personal"},
        )
        self.assertEqual(200, delete_response.status_code)
        delete_payload = delete_response.get_json()
        self.assertEqual(1, delete_payload["deleted_count"])
        self.assertEqual(0, delete_payload["not_found_count"])

        invalid_date = self.client.post(
            "/api/v1/date-recall",
            json={"date": "2026/05/12", "user_id": "demo-user", "memory_space": "personal"},
        )
        self.assertEqual(400, invalid_date.status_code)
        self.assertEqual("invalid_date_recall_request", invalid_date.get_json()["error_code"])

        empty_search = self.client.post(
            "/api/v1/search",
            json={"query": "Memory Core", "user_id": "demo-user", "memory_space": "personal", "limit": 5},
        )
        self.assertEqual(0, empty_search.get_json()["raw_count"])

    def test_api_contract_minimum_fields_and_empty_recall_shape(self):
        write_response = self.client.post(
            "/api/v1/write",
            json={
                "items": [
                    {
                        "user_id": "contract-user",
                        "memory_space": "personal",
                        "source_id": "contract-001",
                        "content": "Contract 验收样例。",
                        "source": "contract-test",
                        "event_type": "raw_message",
                        "sender": "user",
                        "occurred_at": "2026-05-12T08:00:00+00:00",
                    }
                ]
            },
        )
        write_payload = write_response.get_json()
        self.assertTrue({"status", "memory_ids", "accepted_count", "rejected_count", "failure_reason"}.issubset(write_payload.keys()))

        search_payload = self.client.post(
            "/api/v1/search",
            json={"query": "Contract", "user_id": "contract-user", "memory_space": "personal", "limit": 5},
        ).get_json()
        self.assertTrue({"status", "hits", "truncated", "raw_count"}.issubset(search_payload.keys()))
        self.assertTrue({"content", "score", "source", "occurred_at", "evidence"}.issubset(search_payload["hits"][0].keys()))

        empty_date_payload = self.client.post(
            "/api/v1/date-recall",
            json={"date": "2026-05-13", "user_id": "contract-user", "memory_space": "personal", "timezone": "UTC"},
        ).get_json()
        self.assertTrue({"status", "hits", "evidence", "hit_count", "truncated", "miss_reason"}.issubset(empty_date_payload.keys()))
        self.assertEqual([], empty_date_payload["hits"])
        self.assertEqual([], empty_date_payload["evidence"])
        self.assertEqual(0, empty_date_payload["hit_count"])
        self.assertEqual("no_results", empty_date_payload["miss_reason"])

        daily_payload = self.client.post(
            "/api/v1/daily-recall",
            json={"date": "2026-05-12", "user_id": "contract-user", "memory_space": "personal", "timezone": "UTC"},
        ).get_json()
        self.assertTrue({"status", "evidence", "hit_count", "truncated", "daily_recall"}.issubset(daily_payload.keys()))

        delete_payload = self.client.post(
            "/api/v1/delete",
            json={"ids": write_payload["memory_ids"], "user_id": "contract-user", "memory_space": "personal"},
        ).get_json()
        self.assertTrue({"status", "deleted_count", "not_found_count", "failure_reason"}.issubset(delete_payload.keys()))

        export_payload = self.client.get(
            "/api/v1/export?user_id=contract-user&memory_space=personal&format=json"
        ).get_json()
        self.assertTrue({"status", "export_id", "count", "format", "filters", "items"}.issubset(export_payload.keys()))


class MemoryCoreStoreMethodTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        self.store = SQLiteMemoryStore(db_path)
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_store_supports_timeline_fact_slot_and_reference_helpers(self):
        write_result = self.store.write_items(
            [
                {
                    "user_id": "demo-user",
                    "memory_space": "personal",
                    "source_id": "msg-100",
                    "content": "今天确认先把 Core 范围钉死。",
                    "source": "store-test",
                    "event_type": "raw_message",
                    "occurred_at": "2026-05-12T11:00:00+00:00",
                },
                {
                    "user_id": "demo-user",
                    "memory_space": "personal",
                    "source_id": "msg-101",
                    "content": "下一步开始迁 memory_db 的数据平面。",
                    "source": "store-test",
                    "event_type": "raw_message",
                    "occurred_at": "2026-05-12T12:00:00+00:00",
                },
            ]
        )
        first_id = write_result["memory_ids"][0]
        second_id = write_result["memory_ids"][1]

        timeline_rows = self.store.list_timeline_events(
            user_id="demo-user",
            memory_space="personal",
            limit=2,
            event_type="raw_message",
        )
        self.assertEqual(2, len(timeline_rows))
        self.assertEqual(second_id, timeline_rows[0]["id"])

        matched_rows = self.store.search_timeline_events(
            "Core 范围",
            user_id="demo-user",
            memory_space="personal",
            limit=5,
        )
        self.assertEqual(1, len(matched_rows))
        self.assertEqual(first_id, matched_rows[0]["id"])

        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO bio_facts (id, user_id, memory_space, source_id, ts, occurred_at, category, content, confidence, memory_type, subtype, source_ref, status, source_type, answer_kind, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "fact-1",
                    "demo-user",
                    "personal",
                    "fact-source-1",
                    1747047600,
                    "2026-05-12T13:00:00+00:00",
                    "personal",
                    "用户确认新产品架构按 4 段推进。",
                    1.0,
                    "fact",
                    "",
                    "manual",
                    "active",
                    "manual",
                    "fact",
                    "2026-05-12T13:00:00+00:00",
                ),
            )
            connection.commit()

        fact_rows = self.store.search_facts(
            "4 段",
            user_id="demo-user",
            memory_space="personal",
            limit=5,
        )
        self.assertEqual(1, len(fact_rows))
        self.assertEqual("fact-1", fact_rows[0]["id"])

        episode_id = self.store.save_episode(
            "晚上做了 Day 8 数据平面梳理。",
            category="nightly_reflection",
            source="store-test",
            extra={"logical_date": "2026-05-12"},
            user_id="demo-user",
            memory_space="personal",
            source_id="episode-source-1",
            occurred_at="2026-05-12T20:30:00+00:00",
        )
        self.assertTrue(episode_id)
        material_id = self.store.save_distillation_material(
            "daily_digest",
            "Day 8 已开始补齐 episodes 和 distillation_materials 数据平面。",
            title="架构里程碑",
            source_ref="daily-digest-001",
            user_id="demo-user",
            memory_space="personal",
            source_id="material-source-1",
            occurred_at="2026-05-12T21:00:00+00:00",
        )
        self.assertTrue(material_id)
        episode_rows = self.store.search_episodes(
            "nightly",
            user_id="demo-user",
            memory_space="personal",
            limit=5,
        )
        self.assertEqual(1, len(episode_rows))
        self.assertEqual(episode_id, episode_rows[0]["id"])
        material_rows = self.store.search_distillation_materials(
            "架构里程碑",
            user_id="demo-user",
            memory_space="personal",
            limit=5,
        )
        self.assertEqual(1, len(material_rows))
        self.assertEqual(material_id, material_rows[0]["id"])

        slot_id = self.store.upsert_fact_slot(
            topic="个人档案",
            fact_key="架构阶段",
            value_text="Day 6 已完成",
            user_id="demo-user",
            memory_space="personal",
            source_id="slot-source-1",
            occurred_at="2026-05-12T14:00:00+00:00",
        )
        self.assertTrue(slot_id)
        slot = self.store.get_fact_slot(
            "个人档案",
            "架构阶段",
            user_id="demo-user",
            memory_space="personal",
        )
        self.assertEqual("Day 6 已完成", slot["value_text"])
        newer_slot_id = self.store.upsert_fact_slot(
            topic="个人档案",
            fact_key="架构阶段",
            value_text="Day 7 开发中",
            user_id="demo-user",
            memory_space="personal",
            source_id="slot-source-2",
            occurred_at="2026-05-12T15:00:00+00:00",
        )
        self.assertTrue(newer_slot_id)
        slot = self.store.get_fact_slot(
            "个人档案",
            "架构阶段",
            user_id="demo-user",
            memory_space="personal",
        )
        self.assertEqual("Day 7 开发中", slot["value_text"])
        with self.store._connect() as connection:
            active_slot_count = connection.execute(
                "SELECT COUNT(*) FROM fact_slots WHERE user_id=? AND memory_space=? AND topic=? AND fact_key=? AND status='active'",
                ("demo-user", "personal", "个人档案", "架构阶段"),
            ).fetchone()[0]
        self.assertEqual(1, active_slot_count)
        ordered_slot_id = self.store.upsert_fact_slot(
            topic="个人档案",
            fact_key="阶段排序保护",
            value_text="最新版本",
            source_fact_id="10",
            user_id="demo-user",
            memory_space="personal",
            source_id="slot-order-1",
            occurred_at="2026-05-12T15:05:00+00:00",
        )
        stale_slot_id = self.store.upsert_fact_slot(
            topic="个人档案",
            fact_key="阶段排序保护",
            value_text="旧版本",
            source_fact_id="5",
            user_id="demo-user",
            memory_space="personal",
            source_id="slot-order-2",
            occurred_at="2026-05-12T15:06:00+00:00",
        )
        self.assertEqual(ordered_slot_id, stale_slot_id)
        protected_slot = self.store.get_fact_slot(
            "个人档案",
            "阶段排序保护",
            user_id="demo-user",
            memory_space="personal",
        )
        self.assertEqual("最新版本", protected_slot["value_text"])
        searched_slots = self.store.search_fact_slots(
            "阶段",
            user_id="demo-user",
            memory_space="personal",
            limit=10,
        )
        self.assertEqual(2, len(searched_slots))
        self.assertTrue(
            self.store.has_recent_fact_slot_update(
                1778597000,
                topic_prefix="个人",
                user_id="demo-user",
                memory_space="personal",
            )
        )
        slot_hits = self.store.search(
            query="Day 7",
            user_id="demo-user",
            memory_space="personal",
            limit=5,
        )
        self.assertTrue(any(hit["source"] == "fact_slot" for hit in slot_hits["hits"]))
        timeline_hits = self.store.search(
            query="架构里程碑",
            user_id="demo-user",
            memory_space="personal",
            limit=10,
        )
        self.assertTrue(any(hit["source"] == "timeline_material" for hit in timeline_hits["hits"]))
        date_payload = self.store.date_recall(
            day="2026-05-12",
            user_id="demo-user",
            memory_space="personal",
            timezone_name="UTC",
            limit=10,
        )
        date_sources = {hit["source"] for hit in date_payload["hits"]}
        self.assertIn("timeline_episode", date_sources)
        self.assertIn("timeline_material", date_sources)

        reference_id = self.store.save_event_reference(
            source_event_id=first_id,
            target_event_id=second_id,
            user_id="demo-user",
            memory_space="personal",
            source_id="ref-source-1",
            reason="第二条是第一条的后续推进",
            score=0.91,
        )
        self.assertTrue(reference_id)
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT source_event_id, target_event_id, reason, score FROM event_references WHERE id=? LIMIT 1",
                (reference_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(first_id, row["source_event_id"])
        self.assertEqual(second_id, row["target_event_id"])
        self.assertEqual("第二条是第一条的后续推进", row["reason"])

        export_payload = self.store.export_entries(
            user_id="demo-user",
            memory_space="personal",
            limit=10,
        )
        self.assertEqual(7, export_payload["count"])
        export_sources = {item["source"] for item in export_payload["items"]}
        self.assertIn("bio_fact", export_sources)
        self.assertIn("fact_slot", export_sources)
        self.assertIn("timeline_episode", export_sources)
        self.assertIn("timeline_material", export_sources)

        delete_slot_result = self.store.delete_by_ids(
            [newer_slot_id, episode_id, material_id],
            user_id="demo-user",
            memory_space="personal",
        )
        self.assertEqual(3, delete_slot_result["deleted_count"])
        self.assertFalse(
            self.store.get_fact_slot(
                "个人档案",
                "架构阶段",
                user_id="demo-user",
                memory_space="personal",
            )
        )
        self.assertEqual(
            0,
            len(
                self.store.search_episodes(
                    "nightly",
                    user_id="demo-user",
                    memory_space="personal",
                    limit=5,
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                self.store.search_distillation_materials(
                    "架构里程碑",
                    user_id="demo-user",
                    memory_space="personal",
                    limit=5,
                )
            ),
        )


class MemoryCoreExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        self.store = SQLiteMemoryStore(db_path)
        self.store.initialize()
        self.executor = MemoryCoreExecutor(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_executor_date_scope_filters_non_target_date_mentions(self):
        write_result = self.store.write_items(
            [
                {
                    "user_id": "demo-user",
                    "memory_space": "personal",
                    "source_id": "msg-date-filter-1",
                    "content": "今天先记一下 2026-05-13 再处理，不是 2026-05-12 的正式结果。",
                    "source": "executor-test",
                    "event_type": "raw_message",
                    "sender": "user",
                    "occurred_at": "2026-05-12T09:30:00+00:00",
                }
            ]
        )
        self.assertEqual(1, write_result["accepted_count"])

        result = self.executor.date_recall(
            day="2026-05-12",
            user_id="demo-user",
            memory_space="personal",
            timezone_name="UTC",
            limit=10,
        )
        self.assertEqual(0, result["hit_count"])
        self.assertEqual("no_results", result["miss_reason"])
        self.assertTrue(result["date_scope"]["enabled"])
        self.assertEqual(1, result["date_scope"]["filtered_count"])

        daily_result = self.executor.daily_recall(
            day="2026-05-12",
            user_id="demo-user",
            memory_space="personal",
            timezone_name="UTC",
            limit=10,
        )
        self.assertEqual(0, daily_result["daily_recall"]["entry_count"])
        self.assertEqual(["2026-05-12"], daily_result["daily_recall"]["target_dates"])


class MemoryCoreNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        self.store = SQLiteMemoryStore(db_path)
        self.store.initialize()
        self.executor = MemoryCoreExecutor(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalizer_wraps_daily_recall_result(self):
        write_result = self.store.write_items(
            [
                {
                    "user_id": "demo-user",
                    "memory_space": "personal",
                    "source_id": "msg-normalizer-1",
                    "content": "今天上午继续推进 Day 9 executor。",
                    "source": "normalizer-test",
                    "event_type": "raw_message",
                    "sender": "user",
                    "occurred_at": "2026-05-12T09:15:00+00:00",
                }
            ]
        )
        self.assertEqual(1, write_result["accepted_count"])

        result = self.executor.daily_recall(
            day="2026-05-12",
            user_id="demo-user",
            memory_space="personal",
            timezone_name="UTC",
            limit=10,
        )
        normalized = normalize_memory_evidence(
            tool_name="daily_recall",
            arguments={"date": "2026-05-12"},
            result=result,
        )
        self.assertEqual("daily_recall", normalized["tool"])
        self.assertEqual("found", normalized["status"])
        self.assertEqual("daily_recall", normalized["route"])
        self.assertEqual("2026-05-12", normalized["date"])
        self.assertTrue(normalized["date_scope"]["enabled"])
        self.assertEqual(1, normalized["daily_recall"]["entry_count"])
        self.assertTrue(normalized["evidence"])


class MemoryCoreIntegrationSampleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = f"{self.temp_dir.name}/memory_core.db"
        self.port = self._free_port()
        app = create_app(Settings(database_path=db_path, host="127.0.0.1", port=self.port))
        self.server = make_server("127.0.0.1", self.port, app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.temp_dir.cleanup()

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    def test_personal_core_http_integration_sample_runs(self):
        result = run_personal_integration_sample(self.base_url)
        self.assertEqual("ok", result["write"]["status"])
        self.assertGreaterEqual(result["search"]["raw_count"], 1)
        self.assertGreaterEqual(result["daily_recall"]["daily_recall"]["entry_count"], 1)
        self.assertTrue(result["export"]["export_id"])


if __name__ == "__main__":
    unittest.main()