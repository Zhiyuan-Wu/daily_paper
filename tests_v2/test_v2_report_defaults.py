from __future__ import annotations

from v2.contracts.report import DailyReportTaskRequest


def test_daily_report_task_request_defaults_should_follow_runtime_policy():
    req = DailyReportTaskRequest(report_date="2026-03-01")

    assert req.sources == ["arxiv", "huggingface"]
    assert req.window_days == 7
    assert req.arxiv_categories == ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "stat.ML"]
