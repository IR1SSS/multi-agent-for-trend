from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.deps import SessionDep
from app.domain.services.ops_console_service import OpsConsoleService

router = APIRouter(tags=["ops"])


@router.get("/ops", response_class=HTMLResponse)
async def ops_console(session: SessionDep):
    overview = await OpsConsoleService(session).build_overview()
    body = _render_ops_overview_page(overview)
    return HTMLResponse(_page_shell(title="BeautyQA Runtime Ops", hero=_overview_hero(overview), body=body))


@router.get("/ops/overview.json", response_class=JSONResponse)
async def ops_console_overview(session: SessionDep):
    overview = await OpsConsoleService(session).build_overview()
    return JSONResponse(overview)


@router.get("/ops/batches/{run_id}", response_class=HTMLResponse)
async def ops_batch_detail(run_id: str, session: SessionDep):
    detail = await OpsConsoleService(session).build_batch_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"runtime batch not found: {run_id}")
    body = _render_batch_detail_page(detail)
    return HTMLResponse(_page_shell(title=f"Batch {run_id}", hero=_batch_hero(detail), body=body))


@router.get("/ops/batches/{run_id}/detail.json", response_class=JSONResponse)
async def ops_batch_detail_json(run_id: str, session: SessionDep):
    detail = await OpsConsoleService(session).build_batch_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"runtime batch not found: {run_id}")
    return JSONResponse(detail)


@router.get("/ops/tasks/{task_id}", response_class=HTMLResponse)
async def ops_task_detail(task_id: int, session: SessionDep):
    detail = await OpsConsoleService(session).build_task_detail(task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"crawl task not found: {task_id}")
    body = _render_task_detail_page(detail)
    return HTMLResponse(_page_shell(title=f"Task {task_id}", hero=_task_hero(detail), body=body))


@router.get("/ops/tasks/{task_id}/detail.json", response_class=JSONResponse)
async def ops_task_detail_json(task_id: int, session: SessionDep):
    detail = await OpsConsoleService(session).build_task_detail(task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"crawl task not found: {task_id}")
    return JSONResponse(detail)


def _page_shell(*, title: str, hero: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{h(title)}</title>
  <style>
    :root {{
      --bg: #f3efe5;
      --paper: #fffaf1;
      --ink: #1d2b24;
      --muted: #5e6a64;
      --line: #d8cfbe;
      --accent: #b35c2e;
      --accent-soft: #f4dfd1;
      --ok: #356859;
      --warn: #a56a00;
      --bad: #9c2f2f;
      --shadow: rgba(29, 43, 36, 0.08);
      --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(circle at top left, #f8e4d6 0, transparent 28%),
        linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .page {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 20px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, #fff7ee 0%, #fffaf4 60%, #f6ecdf 100%);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 24px;
      box-shadow: 0 10px 30px var(--shadow);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.05;
      letter-spacing: -0.02em;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      max-width: 860px;
      line-height: 1.5;
    }}
    .hero-meta {{
      margin-top: 14px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 14px;
    }}
    .toolbar {{
      margin-top: 14px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      color: var(--ink);
    }}
    .chips {{
      margin-top: 14px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .chip {{
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      gap: 16px;
      margin-top: 18px;
    }}
    .cards {{
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }}
    .card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 8px 20px var(--shadow);
      min-width: 0;
    }}
    .card h2, .section h2 {{
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: -0.01em;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-value {{
      margin-top: 8px;
      font-size: 34px;
      line-height: 1;
    }}
    .section-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .section-wide {{
      grid-column: span 2;
    }}
    .section {{
      background: rgba(255, 250, 241, 0.88);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: 0 8px 24px var(--shadow);
      overflow: hidden;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      margin-bottom: 10px;
    }}
    .section-note {{
      color: var(--muted);
      font-size: 13px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-top: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      font-weight: 600;
    }}
    .kv-table th {{
      width: 220px;
      white-space: nowrap;
    }}
    .tag {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      line-height: 1;
      border: 1px solid var(--line);
      background: #fff;
      margin-right: 6px;
      margin-bottom: 6px;
      white-space: nowrap;
    }}
    .ok {{ color: var(--ok); }}
    .warn {{ color: var(--warn); }}
    .bad {{ color: var(--bad); }}
    .mono {{
      font-family: var(--mono);
      font-size: 12px;
      word-break: break-all;
    }}
    .subgrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .empty {{
      border-top: 1px solid var(--line);
      padding-top: 12px;
      color: var(--muted);
      font-size: 14px;
    }}
    .codebox {{
      margin: 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.62);
      font-family: var(--mono);
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.5;
    }}
    @media (max-width: 1120px) {{
      .cards {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .section-grid {{ grid-template-columns: 1fr; }}
      .section-wide {{ grid-column: auto; }}
      .subgrid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 32px; }}
      .hero h1 {{ font-size: 28px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric-value {{ font-size: 28px; }}
      .kv-table th {{ width: 160px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {hero}
    {body}
  </div>
</body>
</html>"""


def _overview_hero(overview: dict[str, Any]) -> str:
    cards = overview.get("summary_cards", {})
    return f"""
    <section class="hero">
      <h1>BeautyQA Runtime Ops Console</h1>
      <p>Readonly operator view for the front-half pipeline: seed, expansion, schedule, crawl, signal, export. This page shows first-party runtime truth and current QA handoff state.</p>
      <div class="hero-meta">
        <span>Generated: {h(overview.get("generated_at", ""))}</span>
        <span><a href="/ops/overview.json">Open JSON overview</a></span>
      </div>
      <div class="chips">
        <span class="chip">active keywords: {int(cards.get("active_keywords", 0) or 0)}</span>
        <span class="chip">approved expansions: {int(cards.get("approved_expansions", 0) or 0)}</span>
        <span class="chip">due query units: {int(cards.get("due_query_units", 0) or 0)}</span>
        <span class="chip">running batches: {int(cards.get("running_batches", 0) or 0)}</span>
        <span class="chip">failed tasks: {int(cards.get("failed_tasks", 0) or 0)}</span>
        <span class="chip">current export rows: {int(cards.get("current_export_rows", 0) or 0)}</span>
      </div>
    </section>"""


def _batch_hero(detail: dict[str, Any]) -> str:
    run = detail.get("run", {})
    stats = detail.get("stats", {})
    return f"""
    <section class="hero">
      <h1>Runtime Batch Detail</h1>
      <p>This page shows one runtime wave as a first-party execution object, including batch metadata, item states, events, and linked crawl tasks.</p>
      <div class="hero-meta">
        <span>Run ID: <span class="mono">{h(run.get("run_id", ""))}</span></span>
        <span>Generated: {h(detail.get("generated_at", ""))}</span>
        <span><a href="/ops/batches/{h(run.get('run_id', ''))}/detail.json">Open JSON detail</a></span>
      </div>
      <div class="toolbar">
        <a class="btn" href="/ops">Back to overview</a>
      </div>
      <div class="chips">
        <span class="chip">status: {h(run.get("status", ""))}</span>
        <span class="chip">completion: {h(run.get("completion_classification", ""))}</span>
        <span class="chip">linked tasks: {h(stats.get("linked_task_count", 0))}</span>
        <span class="chip">platforms: {h(", ".join(run.get("platforms", []) or []))}</span>
      </div>
    </section>"""


def _task_hero(detail: dict[str, Any]) -> str:
    task = detail.get("task", {})
    return f"""
    <section class="hero">
      <h1>Crawl Task Detail</h1>
      <p>This page exposes one concrete task boundary: task config, crawler runtime result, related batch linkage, query state, and execution logs.</p>
      <div class="hero-meta">
        <span>Task ID: <span class="mono">{h(task.get("id", ""))}</span></span>
        <span>Generated: {h(detail.get("generated_at", ""))}</span>
        <span><a href="/ops/tasks/{h(task.get('id', ''))}/detail.json">Open JSON detail</a></span>
      </div>
      <div class="toolbar">
        <a class="btn" href="/ops">Back to overview</a>
      </div>
      <div class="chips">
        <span class="chip">platform: {h(task.get("platform", ""))}</span>
        <span class="chip">status: {h(task.get("status", ""))}</span>
        <span class="chip">account: {h(task.get("account_id", ""))}</span>
        <span class="chip">keyword: {h(task.get("keyword", ""))}</span>
      </div>
    </section>"""


def _render_ops_overview_page(overview: dict[str, Any]) -> str:
    cards = overview.get("summary_cards", {})
    keywords = overview.get("keywords", {}).get("items", [])
    expansions = overview.get("expansions", {}).get("items", [])
    due_queue = overview.get("due_queue", {}).get("items", [])
    batch_runs = overview.get("batch_runs", {}).get("items", [])
    tasks = overview.get("tasks", {}).get("items", [])
    export_state = overview.get("export_state", {})
    platform_health = overview.get("platform_health", {}).get("items", [])

    return f"""
    <section class="grid cards">
      {metric_card("Active Keywords", cards.get("active_keywords", 0), "Seed layer")}
      {metric_card("Approved Expansions", cards.get("approved_expansions", 0), "Registry")}
      {metric_card("Due Query Units", cards.get("due_query_units", 0), "Schedule")}
      {metric_card("Running Batches", cards.get("running_batches", 0), "INT-002")}
      {metric_card("Failed Tasks", cards.get("failed_tasks", 0), "Diagnostics")}
      {metric_card("Current Export Rows", cards.get("current_export_rows", 0), "QA handoff")}
    </section>

    <section class="grid section-grid">
      <div class="section">
        <div class="section-head">
          <h2>Seeds</h2>
          <div class="section-note">Top active trend keywords</div>
        </div>
        {render_keywords_table(keywords)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Approved Expansions</h2>
          <div class="section-note">Readonly registry view</div>
        </div>
        {render_expansions_table(expansions)}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Due Queue</h2>
          <div class="section-note">Next query units in schedule order</div>
        </div>
        {render_due_queue_table(due_queue)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Batch Runs</h2>
          <div class="section-note">Recent runtime waves</div>
        </div>
        {render_batch_runs_table(batch_runs)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Task Diagnostics</h2>
          <div class="section-note">Recent crawl task state</div>
        </div>
        {render_tasks_table(tasks)}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Export And QA Handoff</h2>
          <div class="section-note">Current manifest and sample signal rows</div>
        </div>
        <div class="subgrid">
          <div>{render_export_manifest(export_state)}</div>
          <div>{render_export_samples(export_state)}</div>
        </div>
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Platform Health</h2>
          <div class="section-note">Account-side readonly snapshot</div>
        </div>
        {render_platform_health(platform_health)}
      </div>
    </section>"""


def _render_batch_detail_page(detail: dict[str, Any]) -> str:
    run = detail.get("run", {})
    stats = detail.get("stats", {})
    items = detail.get("items", [])
    events = detail.get("events", [])
    linked_tasks = detail.get("linked_tasks", [])
    summary_rows = [
        ("Run ID", run.get("run_id", "")),
        ("Run Type", run.get("run_type", "")),
        ("Trigger Source", run.get("trigger_source", "")),
        ("Profile", run.get("profile_name", "")),
        ("Status", run.get("status", "")),
        ("Completion", run.get("completion_classification", "")),
        ("Platforms", ", ".join(run.get("platforms", []) or [])),
        ("Started At", run.get("started_at", "")),
        ("Completed At", run.get("completed_at", "")),
        ("Error", run.get("error_message", "")),
    ]
    return f"""
    <section class="grid cards">
      {metric_card("Linked Tasks", stats.get("linked_task_count", 0), "Task linkage")}
      {metric_card("Item States", len(stats.get("item_status_counts", {})), "Distinct statuses")}
      {metric_card("Event Types", len(stats.get("event_type_counts", {})), "Distinct events")}
      {metric_card("Batch Items", len(items), "Recent items")}
      {metric_card("Events", len(events), "Recent events")}
      {metric_card("Tasks In View", len(linked_tasks), "Recent linked tasks")}
    </section>

    <section class="grid section-grid">
      <div class="section">
        <div class="section-head">
          <h2>Run Summary</h2>
          <div class="section-note">Core batch metadata</div>
        </div>
        {render_kv_table(summary_rows)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Status Aggregates</h2>
          <div class="section-note">Item and event distributions</div>
        </div>
        {render_stat_blocks([("Item Status Counts", stats.get("item_status_counts", {})), ("Event Type Counts", stats.get("event_type_counts", {}))])}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Batch Items</h2>
          <div class="section-note">Execution units and retry state</div>
        </div>
        {render_batch_items_table(items)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Linked Tasks</h2>
          <div class="section-note">Jump to task diagnostics</div>
        </div>
        {render_linked_tasks_table(linked_tasks)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Recent Events</h2>
          <div class="section-note">Planner and runtime audit events</div>
        </div>
        {render_batch_events_table(events)}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Runtime Payloads</h2>
          <div class="section-note">Effective options, summary, and reports</div>
        </div>
        <div class="subgrid">
          <div>{render_json_panel("Requested Options", run.get("requested_options", {}))}</div>
          <div>{render_json_panel("Effective Options", run.get("effective_options", {}))}</div>
          <div>{render_json_panel("Summary", run.get("summary", {}))}</div>
          <div>{render_json_panel("Report Paths", run.get("report_paths", {}))}</div>
        </div>
      </div>
    </section>"""


def _render_task_detail_page(detail: dict[str, Any]) -> str:
    task = detail.get("task", {})
    query_state = detail.get("query_state")
    batch_items = detail.get("batch_items", [])
    events = detail.get("events", [])
    logs = detail.get("logs", [])
    crawler_runtime = task.get("crawler_runtime", {})
    signal_generation = task.get("signal_generation", {})
    summary_rows = [
        ("Task ID", task.get("id", "")),
        ("Platform", task.get("platform", "")),
        ("Keyword", task.get("keyword", "")),
        ("Status", task.get("status", "")),
        ("Account ID", task.get("account_id", "")),
        ("Started At", task.get("started_at", "")),
        ("Completed At", task.get("completed_at", "")),
        ("Error", task.get("error_message", "")),
    ]
    return f"""
    <section class="grid cards">
      {metric_card("Logs", len(logs), "Execution log rows")}
      {metric_card("Batch Links", len(batch_items), "Runtime items")}
      {metric_card("Events", len(events), "Related events")}
      {metric_card("Exit Code", crawler_runtime.get("exit_code", ""), "Crawler runtime")}
      {metric_card("Cleaned Count", task.get("result_summary", {}).get("cleaned_count", 0), "Cleaning")}
      {metric_card("Signal Count", signal_generation.get("signal_count", 0), "Signal generation")}
    </section>

    <section class="grid section-grid">
      <div class="section">
        <div class="section-head">
          <h2>Task Summary</h2>
          <div class="section-note">Primary task boundary fields</div>
        </div>
        {render_kv_table(summary_rows)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Query Schedule Link</h2>
          <div class="section-note">Latest related schedule state</div>
        </div>
        {render_query_state(query_state)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Crawler Runtime</h2>
          <div class="section-note">Vendor boundary and exit status</div>
        </div>
        {render_json_panel("crawler_runtime", crawler_runtime)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Signal Generation</h2>
          <div class="section-note">First-party cleaning and signal output</div>
        </div>
        {render_json_panel("signal_generation", signal_generation)}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Task Config And Result Summary</h2>
          <div class="section-note">Debug payloads used by runtime</div>
        </div>
        <div class="subgrid">
          <div>{render_json_panel("config", task.get("config", {}))}</div>
          <div>{render_json_panel("result_summary", task.get("result_summary", {}))}</div>
        </div>
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Linked Batch Items</h2>
          <div class="section-note">Batch-side task attachment</div>
        </div>
        {render_task_batch_items_table(batch_items)}
      </div>

      <div class="section">
        <div class="section-head">
          <h2>Related Events</h2>
          <div class="section-note">Recent runtime event audit</div>
        </div>
        {render_task_events_table(events)}
      </div>

      <div class="section section-wide">
        <div class="section-head">
          <h2>Execution Logs</h2>
          <div class="section-note">Latest crawl_task_logs rows</div>
        </div>
        {render_task_logs_table(logs)}
      </div>
    </section>"""


def metric_card(title: str, value: Any, label: str) -> str:
    return f"""
    <div class="card">
      <div class="metric-label">{h(label)}</div>
      <div class="metric-value">{h(value)}</div>
      <h2>{h(title)}</h2>
    </div>"""


def render_keywords_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No active keywords yet.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{h(item.get('keyword_id', ''))}</td>"
            f"<td>{h(item.get('keyword', ''))}</td>"
            f"<td>{tag(item.get('priority', ''))}{tag(item.get('risk_flag', ''))}</td>"
            f"<td>{h(item.get('suggested_platforms', ''))}</td>"
            f"<td>{h(item.get('last_crawled_at', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Keyword ID</th><th>Keyword</th><th>Priority / Risk</th>"
        "<th>Platforms</th><th>Last Crawled</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_expansions_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No approved expansions yet.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{h(item.get('normalized_keyword', ''))}</td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('expanded_query', ''))}</td>"
            f"<td>{tag(item.get('expansion_type', ''))}</td>"
            f"<td>{h(item.get('last_seen_at', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Theme</th><th>Platform</th><th>Expanded Query</th>"
        "<th>Type</th><th>Last Seen</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_due_queue_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No active query units yet.</div>'
    rows = []
    for item in items:
        due_class = "ok" if item.get("is_due_now") else ""
        rows.append(
            "<tr>"
            f"<td class='mono'>{h(item.get('query_unit_key', ''))}</td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('expanded_query', ''))}</td>"
            f"<td>{tag(item.get('tier', ''))}</td>"
            f"<td class='{due_class}'>{h(item.get('next_due_at', ''))}</td>"
            f"<td>{h(item.get('last_task_status', ''))}</td>"
            f"<td>{h(item.get('failure_count', 0))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Query Unit</th><th>Platform</th><th>Expanded Query</th>"
        "<th>Tier</th><th>Next Due</th><th>Last Task</th><th>Failures</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_batch_runs_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No runtime batch runs yet.</div>'
    rows = []
    for item in items:
        run_id = item.get("run_id", "")
        status = item.get("status", "")
        rows.append(
            "<tr>"
            f"<td class='mono'><a href='/ops/batches/{h(run_id)}'>{h(run_id)}</a></td>"
            f"<td>{tag(status)}{tag(item.get('completion_classification', ''))}</td>"
            f"<td>{h(item.get('scheduled_task_count', 0))}</td>"
            f"<td>{h(item.get('completed_task_count', 0))}</td>"
            f"<td>{h(item.get('failed_task_count', 0))}</td>"
            f"<td>{h(item.get('generated_signal_count', 0))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Run ID</th><th>Status</th><th>Scheduled</th>"
        "<th>Completed</th><th>Failed</th><th>Signals</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_tasks_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No tasks yet.</div>'
    rows = []
    for item in items:
        error = item.get("crawler_error") or item.get("error_message") or ""
        task_id = item.get("id", "")
        rows.append(
            "<tr>"
            f"<td><a href='/ops/tasks/{h(task_id)}'>{h(task_id)}</a></td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('keyword', ''))}</td>"
            f"<td>{tag(item.get('status', ''))}</td>"
            f"<td>{h(item.get('cleaned_count', 0))} / {h(item.get('signal_count', 0))}</td>"
            f"<td>{h(str(error)[:120])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Task</th><th>Platform</th><th>Keyword</th>"
        "<th>Status</th><th>Cleaned / Signal</th><th>Error</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_export_manifest(export_state: dict[str, Any]) -> str:
    manifest = export_state.get("manifest", {})
    stats = export_state.get("stats", {})
    if not stats.get("manifest_exists"):
        return '<div class="empty">Current handoff manifest is missing.</div>'
    rows = [
        ("Run ID", manifest.get("run_id", "")),
        ("Generated At", manifest.get("generated_at", "")),
        ("Schema Version", manifest.get("schema_version", "")),
        ("Source Runtime Runs", manifest.get("source_runtime_run_count", 0)),
        ("Source Signal Rows", manifest.get("source_signal_row_count", 0)),
        ("Exported Rows", manifest.get("exported_row_count", 0)),
        ("Current JSON", manifest.get("current_json", "")),
        ("Current CSV", manifest.get("current_csv", "")),
    ]
    return render_kv_table(rows)


def render_export_samples(export_state: dict[str, Any]) -> str:
    items = export_state.get("sample_results", [])
    if not items:
        return '<div class="empty">No current exported signal rows available.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td class='mono'>{h(item.get('signal_id', ''))}</td>"
            f"<td>{h(item.get('normalized_keyword', ''))}</td>"
            f"<td>{h(item.get('source_platform', ''))}</td>"
            f"<td>{tag(item.get('confidence', ''))}{tag(item.get('risk_flag', ''))}</td>"
            f"<td>{h(item.get('trend_score', 0))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Signal ID</th><th>Keyword</th><th>Platform</th>"
        "<th>Confidence / Risk</th><th>Score</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_platform_health(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No account records yet.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('active', 0))}</td>"
            f"<td>{h(item.get('expired', 0))}</td>"
            f"<td>{h(item.get('blocked', 0))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Platform</th><th>Active</th><th>Expired</th><th>Blocked</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_kv_table(rows: list[tuple[str, Any]]) -> str:
    body = "".join(
        f"<tr><th>{h(label)}</th><td class='mono'>{h(value)}</td></tr>"
        for label, value in rows
    )
    return f"<table class='kv-table'><tbody>{body}</tbody></table>"


def render_stat_blocks(blocks: list[tuple[str, dict[str, Any]]]) -> str:
    parts = []
    for title, stats in blocks:
        if not stats:
            parts.append(
                f"<div><div class='section-note'>{h(title)}</div><div class='empty'>No rows.</div></div>"
            )
            continue
        rows = "".join(
            f"<tr><th>{h(key)}</th><td class='mono'>{h(value)}</td></tr>"
            for key, value in stats.items()
        )
        parts.append(f"<div><div class='section-note'>{h(title)}</div><table class='kv-table'><tbody>{rows}</tbody></table></div>")
    return "<div class='subgrid'>" + "".join(parts) + "</div>"


def render_json_panel(title: str, payload: Any) -> str:
    text = json.dumps(payload if payload is not None else {}, ensure_ascii=False, indent=2, sort_keys=True)
    return f"<div><div class='section-note'>{h(title)}</div><pre class='codebox'>{h(text)}</pre></div>"


def render_batch_items_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No runtime batch items found.</div>'
    rows = []
    for item in items:
        task_link = (
            f"<a href='/ops/tasks/{h(item.get('task_id', ''))}'>{h(item.get('task_id', ''))}</a>"
            if item.get("task_id")
            else ""
        )
        rows.append(
            "<tr>"
            f"<td class='mono'>{h(item.get('query_unit_key', ''))}</td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('expanded_query', ''))}</td>"
            f"<td>{tag(item.get('item_status', ''))}{tag('retryable' if item.get('retryable') else 'terminal')}</td>"
            f"<td>{h(item.get('attempt_count', 0))}</td>"
            f"<td>{task_link}</td>"
            f"<td>{h(str(item.get('last_error', ''))[:120])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Query Unit</th><th>Platform</th><th>Expanded Query</th>"
        "<th>Status</th><th>Attempts</th><th>Task</th><th>Last Error</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_linked_tasks_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No linked crawl tasks found.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td><a href='/ops/tasks/{h(item.get('id', ''))}'>{h(item.get('id', ''))}</a></td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('keyword', ''))}</td>"
            f"<td>{tag(item.get('status', ''))}</td>"
            f"<td>{h(item.get('account_id', ''))}</td>"
            f"<td>{h(item.get('updated_at', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Task</th><th>Platform</th><th>Keyword</th>"
        "<th>Status</th><th>Account</th><th>Updated</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_batch_events_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No batch events found.</div>'
    rows = []
    for item in items:
        task_link = (
            f"<a href='/ops/tasks/{h(item.get('task_id', ''))}'>{h(item.get('task_id', ''))}</a>"
            if item.get("task_id")
            else ""
        )
        rows.append(
            "<tr>"
            f"<td>{h(item.get('created_at', ''))}</td>"
            f"<td>{tag(item.get('event_type', ''))}</td>"
            f"<td>{h(item.get('platform', ''))}</td>"
            f"<td>{h(item.get('keyword', ''))}</td>"
            f"<td>{task_link}</td>"
            f"<td>{h(str(item.get('message', ''))[:120])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Time</th><th>Event</th><th>Platform</th><th>Keyword</th><th>Task</th><th>Message</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_query_state(item: dict[str, Any] | None) -> str:
    if not item:
        return '<div class="empty">No linked query schedule state found.</div>'
    rows = [
        ("Query Unit", item.get("query_unit_key", "")),
        ("Theme", item.get("normalized_keyword", "")),
        ("Platform", item.get("platform", "")),
        ("Expanded Query", item.get("expanded_query", "")),
        ("Tier", item.get("tier", "")),
        ("Failure Count", item.get("failure_count", 0)),
        ("Last Task Status", item.get("last_task_status", "")),
        ("Next Due At", item.get("next_due_at", "")),
        ("Last Success At", item.get("last_success_at", "")),
        ("Last Failed At", item.get("last_failed_at", "")),
    ]
    return render_kv_table(rows)


def render_task_batch_items_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No related batch items found.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td class='mono'><a href='/ops/batches/{h(item.get('run_id', ''))}'>{h(item.get('run_id', ''))}</a></td>"
            f"<td class='mono'>{h(item.get('query_unit_key', ''))}</td>"
            f"<td>{h(item.get('expanded_query', ''))}</td>"
            f"<td>{tag(item.get('item_status', ''))}</td>"
            f"<td>{h(item.get('attempt_count', 0))}</td>"
            f"<td>{h(str(item.get('last_error', ''))[:120])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Run ID</th><th>Query Unit</th><th>Expanded Query</th>"
        "<th>Status</th><th>Attempts</th><th>Last Error</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_task_events_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No related events found.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{h(item.get('created_at', ''))}</td>"
            f"<td>{tag(item.get('event_type', ''))}</td>"
            f"<td><a href='/ops/batches/{h(item.get('run_id', ''))}'>{h(item.get('run_id', ''))}</a></td>"
            f"<td>{h(str(item.get('message', ''))[:120])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Time</th><th>Event</th><th>Run ID</th><th>Message</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_task_logs_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No crawl_task_logs rows found.</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{h(item.get('created_at', ''))}</td>"
            f"<td>{tag(item.get('level', ''))}</td>"
            f"<td>{h(item.get('message', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def tag(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"<span class='tag'>{h(text)}</span>"


def h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))
