from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.infrastructure.database.models import (
    Account,
    CrawlTask,
    CrawlTaskLog,
    ExpansionRegistry,
    QueryScheduleState,
    RuntimeBatchItem,
    RuntimeBatchRun,
    RuntimeBatchRunEvent,
    TrendKeyword,
)


class OpsConsoleService:
    """Readonly aggregation service for the runtime operations console."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_overview(self) -> dict[str, Any]:
        now = datetime.now()
        keywords = await self._load_keywords()
        expansions = await self._load_expansions()
        due_queue = await self._load_due_queue(now=now)
        batch_runs = await self._load_batch_runs()
        tasks = await self._load_tasks()
        platform_health = await self._load_platform_health()
        export_state = self._load_export_state()

        return {
            "generated_at": now.isoformat(),
            "summary_cards": {
                "active_keywords": keywords["stats"]["active_keywords"],
                "approved_expansions": expansions["stats"]["approved_active"],
                "due_query_units": due_queue["stats"]["due_now"],
                "running_batches": batch_runs["stats"]["running"],
                "failed_tasks": tasks["stats"]["failed"],
                "current_export_rows": export_state["stats"]["exported_row_count"],
            },
            "keywords": keywords,
            "expansions": expansions,
            "due_queue": due_queue,
            "batch_runs": batch_runs,
            "tasks": tasks,
            "platform_health": platform_health,
            "export_state": export_state,
        }

    async def build_batch_detail(self, run_id: str) -> dict[str, Any] | None:
        batch = (
            await self._session.execute(
                select(RuntimeBatchRun).where(RuntimeBatchRun.run_id == run_id).limit(1)
            )
        ).scalar_one_or_none()
        if batch is None:
            return None

        item_rows = (
            await self._session.execute(
                select(RuntimeBatchItem)
                .where(RuntimeBatchItem.run_id == run_id)
                .order_by(RuntimeBatchItem.updated_at.desc(), RuntimeBatchItem.id.desc())
                .limit(80)
            )
        ).scalars().all()
        event_rows = (
            await self._session.execute(
                select(RuntimeBatchRunEvent)
                .where(RuntimeBatchRunEvent.run_id == run_id)
                .order_by(RuntimeBatchRunEvent.created_at.desc(), RuntimeBatchRunEvent.id.desc())
                .limit(80)
            )
        ).scalars().all()

        task_ids = sorted(
            {
                task_id
                for task_id in [*(row.task_id for row in item_rows), *(row.task_id for row in event_rows)]
                if task_id
            }
        )
        tasks_by_id: dict[int, CrawlTask] = {}
        if task_ids:
            task_rows = (
                await self._session.execute(select(CrawlTask).where(CrawlTask.id.in_(task_ids)))
            ).scalars().all()
            tasks_by_id = {int(row.id): row for row in task_rows}

        item_status_counts = await self._count_grouped(
            select(RuntimeBatchItem.item_status, func.count(RuntimeBatchItem.id))
            .where(RuntimeBatchItem.run_id == run_id)
            .group_by(RuntimeBatchItem.item_status)
        )
        event_type_counts = await self._count_grouped(
            select(RuntimeBatchRunEvent.event_type, func.count(RuntimeBatchRunEvent.id))
            .where(RuntimeBatchRunEvent.run_id == run_id)
            .group_by(RuntimeBatchRunEvent.event_type)
        )

        return {
            "generated_at": datetime.now().isoformat(),
            "run": {
                "id": batch.id,
                "run_id": batch.run_id,
                "run_type": batch.run_type,
                "trigger_source": batch.trigger_source,
                "profile_name": batch.profile_name,
                "status": batch.status,
                "completion_classification": batch.completion_classification or "",
                "platforms": batch.platforms or [],
                "requested_options": batch.requested_options or {},
                "effective_options": batch.effective_options or {},
                "summary": batch.summary or {},
                "report_paths": batch.report_paths or {},
                "error_message": batch.error_message or "",
                "started_at": _dt(batch.started_at),
                "completed_at": _dt(batch.completed_at),
                "created_at": _dt(batch.created_at),
                "updated_at": _dt(batch.updated_at),
            },
            "stats": {
                "item_status_counts": item_status_counts,
                "event_type_counts": event_type_counts,
                "linked_task_count": len(task_ids),
            },
            "items": [
                {
                    "id": row.id,
                    "query_unit_key": row.query_unit_key,
                    "keyword": row.keyword or "",
                    "platform": row.platform,
                    "expanded_query": row.expanded_query,
                    "item_status": row.item_status,
                    "retryable": bool(row.retryable),
                    "attempt_count": row.attempt_count,
                    "task_id": row.task_id,
                    "task_status": (tasks_by_id.get(int(row.task_id)).status if row.task_id and tasks_by_id.get(int(row.task_id)) else ""),
                    "last_error": row.last_error or "",
                    "last_heartbeat_at": _dt(row.last_heartbeat_at),
                    "completed_at": _dt(row.completed_at),
                    "updated_at": _dt(row.updated_at),
                    "payload": row.payload or {},
                }
                for row in item_rows
            ],
            "events": [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "platform": row.platform or "",
                    "keyword": row.keyword or "",
                    "task_id": row.task_id,
                    "message": row.message or "",
                    "dedup_key": row.dedup_key or "",
                    "created_at": _dt(row.created_at),
                    "payload": row.payload or {},
                }
                for row in event_rows
            ],
            "linked_tasks": [
                {
                    "id": row.id,
                    "platform": row.platform,
                    "keyword": row.keyword,
                    "status": row.status,
                    "account_id": row.account_id,
                    "created_at": _dt(row.created_at),
                    "updated_at": _dt(row.updated_at),
                }
                for row in sorted(tasks_by_id.values(), key=lambda item: item.updated_at or item.created_at, reverse=True)
            ],
        }

    async def build_task_detail(self, task_id: int) -> dict[str, Any] | None:
        task = (
            await self._session.execute(select(CrawlTask).where(CrawlTask.id == task_id).limit(1))
        ).scalar_one_or_none()
        if task is None:
            return None

        log_rows = (
            await self._session.execute(
                select(CrawlTaskLog)
                .where(CrawlTaskLog.task_id == task_id)
                .order_by(CrawlTaskLog.created_at.desc(), CrawlTaskLog.id.desc())
                .limit(80)
            )
        ).scalars().all()
        batch_item_rows = (
            await self._session.execute(
                select(RuntimeBatchItem)
                .where(RuntimeBatchItem.task_id == task_id)
                .order_by(RuntimeBatchItem.updated_at.desc(), RuntimeBatchItem.id.desc())
                .limit(20)
            )
        ).scalars().all()
        event_rows = (
            await self._session.execute(
                select(RuntimeBatchRunEvent)
                .where(RuntimeBatchRunEvent.task_id == task_id)
                .order_by(RuntimeBatchRunEvent.created_at.desc(), RuntimeBatchRunEvent.id.desc())
                .limit(40)
            )
        ).scalars().all()
        query_state = (
            await self._session.execute(
                select(QueryScheduleState)
                .where(QueryScheduleState.last_task_id == task_id)
                .order_by(QueryScheduleState.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        result_summary = task.result_summary or {}
        crawler_runtime = result_summary.get("crawler_runtime", {}) or {}
        signal_generation = result_summary.get("signal_generation", {}) or {}

        return {
            "generated_at": datetime.now().isoformat(),
            "task": {
                "id": task.id,
                "keyword_id": task.keyword_id,
                "keyword": task.keyword,
                "platform": task.platform,
                "status": task.status,
                "account_id": task.account_id,
                "config": task.config or {},
                "error_message": task.error_message or "",
                "result_summary": result_summary,
                "crawler_runtime": crawler_runtime,
                "signal_generation": signal_generation,
                "started_at": _dt(task.started_at),
                "completed_at": _dt(task.completed_at),
                "created_at": _dt(task.created_at),
                "updated_at": _dt(task.updated_at),
            },
            "query_state": (
                {
                    "id": query_state.id,
                    "query_unit_key": query_state.query_unit_key,
                    "normalized_keyword": query_state.normalized_keyword,
                    "platform": query_state.platform,
                    "expanded_query": query_state.expanded_query,
                    "tier": query_state.tier,
                    "failure_count": query_state.failure_count,
                    "last_task_status": query_state.last_task_status or "",
                    "next_due_at": _dt(query_state.next_due_at),
                    "last_success_at": _dt(query_state.last_success_at),
                    "last_failed_at": _dt(query_state.last_failed_at),
                    "updated_at": _dt(query_state.updated_at),
                }
                if query_state
                else None
            ),
            "batch_items": [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "query_unit_key": row.query_unit_key,
                    "platform": row.platform,
                    "expanded_query": row.expanded_query,
                    "item_status": row.item_status,
                    "retryable": bool(row.retryable),
                    "attempt_count": row.attempt_count,
                    "last_error": row.last_error or "",
                    "updated_at": _dt(row.updated_at),
                }
                for row in batch_item_rows
            ],
            "events": [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "event_type": row.event_type,
                    "platform": row.platform or "",
                    "keyword": row.keyword or "",
                    "message": row.message or "",
                    "dedup_key": row.dedup_key or "",
                    "created_at": _dt(row.created_at),
                    "payload": row.payload or {},
                }
                for row in event_rows
            ],
            "logs": [
                {
                    "id": row.id,
                    "level": row.level,
                    "message": row.message,
                    "created_at": _dt(row.created_at),
                }
                for row in log_rows
            ],
        }

    async def _load_keywords(self) -> dict[str, Any]:
        priority_order = case(
            (TrendKeyword.priority == "high", 0),
            (TrendKeyword.priority == "medium", 1),
            (TrendKeyword.priority == "low", 2),
            else_=3,
        )
        total_keywords = await self._scalar(select(func.count()).select_from(TrendKeyword))
        active_keywords = await self._scalar(
            select(func.count()).select_from(TrendKeyword).where(TrendKeyword.is_active.is_(True))
        )
        high_priority = await self._scalar(
            select(func.count())
            .select_from(TrendKeyword)
            .where(TrendKeyword.is_active.is_(True), TrendKeyword.priority == "high")
        )

        stmt = (
            select(TrendKeyword)
            .where(TrendKeyword.is_active.is_(True))
            .order_by(priority_order.asc(), TrendKeyword.updated_at.desc())
            .limit(10)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {
            "stats": {
                "total_keywords": total_keywords,
                "active_keywords": active_keywords,
                "high_priority": high_priority,
            },
            "items": [
                {
                    "id": row.id,
                    "keyword_id": row.keyword_id,
                    "keyword": row.keyword,
                    "normalized_keyword": row.normalized_keyword,
                    "topic_cluster": row.topic_cluster,
                    "priority": row.priority,
                    "risk_flag": row.risk_flag,
                    "crawl_goal": row.crawl_goal,
                    "suggested_platforms": row.suggested_platforms,
                    "last_crawled_at": _dt(row.last_crawled_at),
                }
                for row in rows
            ],
        }

    async def _load_expansions(self) -> dict[str, Any]:
        approved_active = await self._scalar(
            select(func.count())
            .select_from(ExpansionRegistry)
            .where(
                ExpansionRegistry.is_active.is_(True),
                ExpansionRegistry.status == "approved",
            )
        )
        pending_review = await self._scalar(
            select(func.count())
            .select_from(ExpansionRegistry)
            .where(ExpansionRegistry.review_status == "pending")
        )
        candidate_count = await self._scalar(
            select(func.count())
            .select_from(ExpansionRegistry)
            .where(ExpansionRegistry.status == "candidate")
        )

        stmt = (
            select(ExpansionRegistry)
            .where(
                ExpansionRegistry.is_active.is_(True),
                ExpansionRegistry.status == "approved",
            )
            .order_by(ExpansionRegistry.updated_at.desc())
            .limit(12)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {
            "stats": {
                "approved_active": approved_active,
                "pending_review": pending_review,
                "candidate_count": candidate_count,
            },
            "items": [
                {
                    "id": row.id,
                    "keyword_db_id": row.keyword_db_id,
                    "normalized_keyword": row.normalized_keyword,
                    "platform": row.platform,
                    "expanded_query": row.expanded_query,
                    "expansion_type": row.expansion_type,
                    "review_status": row.review_status,
                    "status": row.status,
                    "last_seen_at": _dt(row.last_seen_at),
                }
                for row in rows
            ],
        }

    async def _load_due_queue(self, *, now: datetime) -> dict[str, Any]:
        due_now = await self._scalar(
            select(func.count())
            .select_from(QueryScheduleState)
            .where(
                QueryScheduleState.is_active.is_(True),
                QueryScheduleState.next_due_at <= now,
            )
        )
        retry_heavy = await self._scalar(
            select(func.count())
            .select_from(QueryScheduleState)
            .where(
                QueryScheduleState.is_active.is_(True),
                QueryScheduleState.failure_count >= 2,
            )
        )

        stmt = (
            select(QueryScheduleState)
            .where(QueryScheduleState.is_active.is_(True))
            .order_by(QueryScheduleState.next_due_at.asc())
            .limit(12)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {
            "stats": {
                "due_now": due_now,
                "retry_heavy": retry_heavy,
            },
            "items": [
                {
                    "id": row.id,
                    "query_unit_key": row.query_unit_key,
                    "normalized_keyword": row.normalized_keyword,
                    "platform": row.platform,
                    "expanded_query": row.expanded_query,
                    "tier": row.tier,
                    "failure_count": row.failure_count,
                    "last_task_status": row.last_task_status or "",
                    "next_due_at": _dt(row.next_due_at),
                    "last_success_at": _dt(row.last_success_at),
                    "last_failed_at": _dt(row.last_failed_at),
                    "is_due_now": bool(row.next_due_at and row.next_due_at <= now),
                }
                for row in rows
            ],
        }

    async def _load_batch_runs(self) -> dict[str, Any]:
        running = await self._scalar(
            select(func.count()).select_from(RuntimeBatchRun).where(RuntimeBatchRun.status == "running")
        )
        failed = await self._scalar(
            select(func.count()).select_from(RuntimeBatchRun).where(RuntimeBatchRun.status == "failed")
        )
        completed = await self._scalar(
            select(func.count()).select_from(RuntimeBatchRun).where(RuntimeBatchRun.status == "completed")
        )
        stmt = select(RuntimeBatchRun).order_by(RuntimeBatchRun.started_at.desc()).limit(8)
        rows = (await self._session.execute(stmt)).scalars().all()
        return {
            "stats": {
                "running": running,
                "failed": failed,
                "completed": completed,
            },
            "items": [
                {
                    "run_id": row.run_id,
                    "run_type": row.run_type,
                    "profile_name": row.profile_name,
                    "status": row.status,
                    "completion_classification": row.completion_classification or "",
                    "started_at": _dt(row.started_at),
                    "completed_at": _dt(row.completed_at),
                    "scheduled_task_count": int((row.summary or {}).get("scheduled_task_count", 0) or 0),
                    "completed_task_count": int((row.summary or {}).get("completed_task_count", 0) or 0),
                    "failed_task_count": int((row.summary or {}).get("failed_task_count", 0) or 0),
                    "generated_signal_count": int((row.summary or {}).get("generated_signal_count", 0) or 0),
                }
                for row in rows
            ],
        }

    async def _load_tasks(self) -> dict[str, Any]:
        running = await self._scalar(select(func.count()).select_from(CrawlTask).where(CrawlTask.status == "running"))
        failed = await self._scalar(select(func.count()).select_from(CrawlTask).where(CrawlTask.status == "failed"))
        completed = await self._scalar(
            select(func.count()).select_from(CrawlTask).where(CrawlTask.status == "completed")
        )
        stmt = select(CrawlTask).order_by(CrawlTask.updated_at.desc()).limit(12)
        rows = (await self._session.execute(stmt)).scalars().all()
        return {
            "stats": {
                "running": running,
                "failed": failed,
                "completed": completed,
            },
            "items": [
                {
                    "id": row.id,
                    "keyword_id": row.keyword_id,
                    "keyword": row.keyword,
                    "platform": row.platform,
                    "status": row.status,
                    "account_id": row.account_id,
                    "error_message": row.error_message or "",
                    "created_at": _dt(row.created_at),
                    "updated_at": _dt(row.updated_at),
                    "crawler_exit_code": (row.result_summary or {}).get("crawler_runtime", {}).get("exit_code"),
                    "crawler_status": (row.result_summary or {}).get("crawler_runtime", {}).get("status", ""),
                    "crawler_error": (row.result_summary or {}).get("crawler_runtime", {}).get("error_message", ""),
                    "cleaned_count": int((row.result_summary or {}).get("cleaned_count", 0) or 0),
                    "signal_count": int(
                        ((row.result_summary or {}).get("signal_generation", {}) or {}).get("signal_count", 0) or 0
                    ),
                }
                for row in rows
            ],
        }

    async def _load_platform_health(self) -> dict[str, Any]:
        rows = (
            await self._session.execute(
                select(Account.platform, Account.status, func.count(Account.id))
                .group_by(Account.platform, Account.status)
                .order_by(Account.platform.asc(), Account.status.asc())
            )
        ).all()
        grouped: dict[str, dict[str, int]] = {}
        for platform, status, count in rows:
            platform_stats = grouped.setdefault(platform, {"active": 0, "expired": 0, "blocked": 0})
            platform_stats[str(status)] = int(count or 0)
        items = [
            {
                "platform": platform,
                "active": values.get("active", 0),
                "expired": values.get("expired", 0),
                "blocked": values.get("blocked", 0),
            }
            for platform, values in sorted(grouped.items())
        ]
        return {"items": items}

    def _load_export_state(self) -> dict[str, Any]:
        current_dir = Path(settings.TREND_SIGNAL_HANDOFF_DIR) / "current"
        manifest_path = current_dir / "manifest.json"
        current_json_path = current_dir / "trend_signal_latest.json"
        current_csv_path = current_dir / "trend_signal_latest.csv"

        manifest: dict[str, Any] = {}
        current_results: list[dict[str, Any]] = []

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}

        if current_json_path.exists():
            try:
                payload = json.loads(current_json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            results = payload.get("results", [])
            if isinstance(results, list):
                current_results = [item for item in results if isinstance(item, dict)][:5]

        return {
            "stats": {
                "manifest_exists": manifest_path.exists(),
                "json_exists": current_json_path.exists(),
                "csv_exists": current_csv_path.exists(),
                "exported_row_count": int(manifest.get("exported_row_count", len(current_results)) or 0),
            },
            "manifest": {
                "run_id": manifest.get("run_id", ""),
                "generated_at": manifest.get("generated_at", ""),
                "source_runtime_run_count": int(manifest.get("source_runtime_run_count", 0) or 0),
                "source_signal_row_count": int(manifest.get("source_signal_row_count", 0) or 0),
                "exported_row_count": int(manifest.get("exported_row_count", 0) or 0),
                "schema_version": manifest.get("schema_version", ""),
                "current_json": str(current_json_path),
                "current_csv": str(current_csv_path),
            },
            "sample_results": [
                {
                    "signal_id": row.get("signal_id", ""),
                    "normalized_keyword": row.get("normalized_keyword", ""),
                    "source_platform": row.get("source_platform", ""),
                    "confidence": row.get("confidence", ""),
                    "risk_flag": row.get("risk_flag", ""),
                    "trend_score": row.get("trend_score", 0),
                }
                for row in current_results
            ],
        }

    async def _scalar(self, stmt: Any) -> int:
        value = (await self._session.execute(stmt)).scalar()
        return int(value or 0)

    async def _count_grouped(self, stmt: Any) -> dict[str, int]:
        rows = (await self._session.execute(stmt)).all()
        return {str(key): int(value or 0) for key, value in rows if key is not None}


def _dt(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
