from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from app.domain.services.integration_runtime_service import IntegrationRuntimeService


def _task_payload(*, max_attempts: int = 2) -> dict:
    return {
        "id": 27,
        "keyword_id": 14,
        "keyword": "护肤 热度",
        "platform": "dy",
        "config": {
            "query_unit_key": "护肤__dy__护肤 热度",
            "task_dedup_key": "KW_0014__douyin__护肤 热度",
        },
        "_runtime_policy": {
            "max_raw_items": 1,
            "max_transient_attempts": max_attempts,
            "retry_backoff_seconds": 0,
        },
    }


class Int002TransientRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retryable_failure_then_success_retries_once(self) -> None:
        service = IntegrationRuntimeService()
        service._run_task_pipeline = AsyncMock(side_effect=[
            {
                "task_id": 27,
                "keyword_id": 14,
                "keyword": "护肤 热度",
                "platform": "dy",
                "success": False,
                "cleaned_count": 0,
                "signal_count": 0,
                "signal_output_file": "",
                "error": "Page.goto timeout",
            },
            {
                "task_id": 27,
                "keyword_id": 14,
                "keyword": "护肤 热度",
                "platform": "dy",
                "success": True,
                "cleaned_count": 1,
                "signal_count": 1,
                "signal_output_file": "/tmp/signal.json",
                "error": "",
            },
        ])
        service._record_task_result = AsyncMock()
        service._update_batch_item_from_task_result = AsyncMock()
        service._record_task_retry_event = AsyncMock()
        service._mark_batch_item_retry_dispatched = AsyncMock()

        result = await service._run_task_with_transient_retry(
            batch_run_id=1,
            run_id="int002_test_retry_success",
            task=_task_payload(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["attempt_count"], 2)
        self.assertTrue(result["retry_triggered"])
        self.assertFalse(result["retry_exhausted"])
        self.assertEqual(len(result["attempts"]), 2)
        self.assertTrue(result["attempts"][0]["retryable_error"])
        self.assertFalse(result["attempts"][1]["retryable_error"])
        service._record_task_retry_event.assert_awaited_once()
        service._mark_batch_item_retry_dispatched.assert_awaited_once()

    async def test_retryable_failure_then_failure_exhausts_retry(self) -> None:
        service = IntegrationRuntimeService()
        failing_result = {
            "task_id": 27,
            "keyword_id": 14,
            "keyword": "护肤 热度",
            "platform": "dy",
            "success": False,
            "cleaned_count": 0,
            "signal_count": 0,
            "signal_output_file": "",
            "error": "connection timeout during browser launch",
        }
        service._run_task_pipeline = AsyncMock(side_effect=[failing_result, failing_result])
        service._record_task_result = AsyncMock()
        service._update_batch_item_from_task_result = AsyncMock()
        service._record_task_retry_event = AsyncMock()
        service._mark_batch_item_retry_dispatched = AsyncMock()

        result = await service._run_task_with_transient_retry(
            batch_run_id=1,
            run_id="int002_test_retry_fail",
            task=_task_payload(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["attempt_count"], 2)
        self.assertTrue(result["retry_triggered"])
        self.assertTrue(result["retry_exhausted"])
        self.assertTrue(all(item["retryable_error"] for item in result["attempts"]))
        service._record_task_retry_event.assert_awaited_once()
        service._mark_batch_item_retry_dispatched.assert_awaited_once()

    async def test_terminal_failure_does_not_retry(self) -> None:
        service = IntegrationRuntimeService()
        service._run_task_pipeline = AsyncMock(return_value={
            "task_id": 27,
            "keyword_id": 14,
            "keyword": "护肤 热度",
            "platform": "dy",
            "success": False,
            "cleaned_count": 0,
            "signal_count": 0,
            "signal_output_file": "",
            "error": "schema_mismatch",
        })
        service._record_task_result = AsyncMock()
        service._update_batch_item_from_task_result = AsyncMock()
        service._record_task_retry_event = AsyncMock()
        service._mark_batch_item_retry_dispatched = AsyncMock()

        result = await service._run_task_with_transient_retry(
            batch_run_id=1,
            run_id="int002_test_terminal_fail",
            task=_task_payload(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["attempt_count"], 1)
        self.assertFalse(result["retry_triggered"])
        self.assertFalse(result["retry_exhausted"])
        self.assertFalse(result["attempts"][0]["retryable_error"])
        service._record_task_retry_event.assert_not_called()
        service._mark_batch_item_retry_dispatched.assert_not_called()

