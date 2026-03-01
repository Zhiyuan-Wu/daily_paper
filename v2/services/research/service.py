from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from v2.config import V2Config
from v2.db.models import ResearchReport, ResearchTask
from v2.db.repo import Repo


class ResearchService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config

    def run_task(self, topic: str, constraints: dict[str, str]) -> dict:
        task_id = uuid.uuid4().hex
        workdir = self.config.research_root / task_id
        workdir.mkdir(parents=True, exist_ok=True)
        task_file = workdir / f"task_{task_id}.txt"
        report_file = workdir / "report.md"
        sources_file = workdir / "sources.json"

        task_file.write_text(self._build_task_prompt(topic, constraints), encoding="utf-8")

        task = ResearchTask(
            id=task_id,
            topic=topic,
            constraints_json=json.dumps(constraints, ensure_ascii=False),
            status="running",
            workdir_path=str(workdir),
            task_file_path=str(task_file),
            report_file_path=str(report_file),
            started_at=datetime.now(),
        )
        self.repo.session.add(task)
        self.repo.session.commit()

        try:
            self._run_claude(workdir, task_file)

            if not report_file.exists():
                report_file.write_text(f"# 调研报告\n\n主题：{topic}\n\n（claude 未生成报告，使用兜底内容）", encoding="utf-8")
            if not sources_file.exists():
                sources_file.write_text("[]", encoding="utf-8")

            report_md = report_file.read_text(encoding="utf-8")
            sources = json.loads(sources_file.read_text(encoding="utf-8") or "[]")
            sources = self._normalize_sources(sources)

            self.repo.session.add(
                ResearchReport(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    report_md=report_md,
                    sources_json=json.dumps(sources, ensure_ascii=False),
                )
            )
            task.status = "completed"
            task.finished_at = datetime.now()
            self.repo.session.commit()

            self._cleanup_workdir(task_id, workdir)
            return {"task_id": task_id, "status": "completed"}
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.finished_at = datetime.now()
            self.repo.session.commit()
            self._cleanup_workdir(task_id, workdir)
            return {"task_id": task_id, "status": "failed", "error": str(e)}

    def get_result(self, task_id: str) -> dict:
        report = self.repo.session.query(ResearchReport).filter(ResearchReport.task_id == task_id).first()
        if not report:
            raise FileNotFoundError("RESEARCH_REPORT_NOT_FOUND")
        return {
            "task_id": task_id,
            "report_md": report.report_md,
            "sources": json.loads(report.sources_json or "[]"),
        }

    def get_task(self, task_id: str) -> dict:
        task = self.repo.session.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            raise FileNotFoundError("TASK_NOT_FOUND")
        return {
            "task_id": task.id,
            "status": task.status,
            "error_message": task.error_message,
        }

    def _run_claude(self, workdir: Path, task_file: Path) -> None:
        if os.getenv("V2_RESEARCH_FAKE", "0") == "1":
            (workdir / "report.md").write_text("# 调研报告\n\n这是本地测试模式自动生成的报告。", encoding="utf-8")
            (workdir / "sources.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "Mock Source",
                            "url": "https://example.com/mock",
                            "source": "mock",
                            "published_at": "2026-01-01",
                            "evidence_snippet": "mock evidence",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return

        cmd = [
            "claude",
            f"Read {task_file.resolve()} for work details.",
            "--allowedTools",
            "Bash,Read,Edit,Write,WebFetch",
        ]
        timeout = self.config.research_timeout_minutes * 60
        subprocess.run(cmd, cwd=str(workdir), check=True, timeout=timeout)

    def _normalize_sources(self, sources: list[dict]) -> list[dict]:
        normalized = []
        for src in sources:
            normalized.append(
                {
                    "title": str(src.get("title", "")),
                    "url": str(src.get("url", "")),
                    "source": str(src.get("source", "")),
                    "published_at": str(src.get("published_at", "")),
                    "evidence_snippet": str(src.get("evidence_snippet", ""))[: self.config.evidence_snippet_max_chars],
                }
            )
        return normalized

    def _cleanup_workdir(self, task_id: str, workdir: Path) -> None:
        try:
            shutil.rmtree(workdir, ignore_errors=False)
        except Exception:
            queue_file = self.config.research_root / "cleanup_retry_queue.jsonl"
            queue_file.parent.mkdir(parents=True, exist_ok=True)
            with queue_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"task_id": task_id, "workdir": str(workdir), "time": datetime.now().isoformat()}) + "\n")

    @staticmethod
    def _build_task_prompt(topic: str, constraints: dict[str, str]) -> str:
        lines = [
            "你是深度文献调研助手，请按固定结构输出报告。",
            "输出文件: report.md, sources.json",
            "报告结构: 背景 / 问题拆解 / 方法对比 / 关键文献 / 结论 / 后续行动",
            f"调研主题: {topic}",
            f"约束: {json.dumps(constraints, ensure_ascii=False)}",
        ]
        return "\n".join(lines)
