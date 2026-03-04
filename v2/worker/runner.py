from __future__ import annotations

import json
import shutil
from pathlib import Path


def run_cleanup_retry_queue(queue_file: Path) -> int:
    if not queue_file.exists():
        return 0
    lines = queue_file.read_text(encoding="utf-8").splitlines()
    remained = []
    cleaned = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        workdir = Path(data["workdir"])
        try:
            if workdir.exists():
                shutil.rmtree(workdir)
            cleaned += 1
        except Exception:
            remained.append(line)
    queue_file.write_text("\n".join(remained) + ("\n" if remained else ""), encoding="utf-8")
    return cleaned
