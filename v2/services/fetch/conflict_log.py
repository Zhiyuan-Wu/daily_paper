from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ConflictLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, incoming: dict, matched: dict) -> None:
        record = {
            "time": datetime.now().isoformat(),
            "incoming": incoming,
            "matched": matched,
            "kind": "dedup_conflict_auto_merged",
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
