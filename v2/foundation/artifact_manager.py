from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ArtifactInfo:
    path: Path
    file_hash: str
    size_bytes: int


class ArtifactManager:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def paper_dir(self, paper_uid: str) -> Path:
        path = self.root / "papers" / paper_uid
        path.mkdir(parents=True, exist_ok=True)
        return path

    def pdf_path(self, paper_uid: str) -> Path:
        return self.paper_dir(paper_uid) / "source.pdf"

    def text_path(self, paper_uid: str, method: str) -> Path:
        parsed_dir = self.paper_dir(paper_uid) / "parsed" / "v1"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        return parsed_dir / f"{method}.txt"

    def write_bytes(self, target: Path, content: bytes) -> ArtifactInfo:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        return ArtifactInfo(path=target, file_hash=digest, size_bytes=len(content))

    def write_text(self, target: Path, content: str) -> ArtifactInfo:
        data = content.encode("utf-8")
        return self.write_bytes(target, data)

    @staticmethod
    def paper_uid(source: str, external_id: str) -> str:
        raw = f"{source}:{external_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
