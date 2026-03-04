from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import fitz
import requests

from v2.config import V2Config
from v2.db.repo import Repo
from v2.foundation.artifact_manager import ArtifactManager

logger = logging.getLogger(__name__)


class ParseService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config
        self.artifacts = ArtifactManager(config.artifact_root)

    def parse(self, paper_uid: str, method: str, force_reparse: bool) -> dict:
        if method not in {"simple", "ocr"}:
            raise ValueError("PARSE_METHOD_UNSUPPORTED")

        cached = self.repo.get_artifact(paper_uid, "text", parser_method=method)
        if cached and not force_reparse and Path(cached.path).exists():
            text = Path(cached.path).read_text(encoding="utf-8")
            return {
                "paper_uid": paper_uid,
                "method": method,
                "text_path": cached.path,
                "cached": True,
                "char_count": len(text),
            }

        pdf_artifact = self.repo.get_artifact(paper_uid, "pdf")
        if not pdf_artifact or not Path(pdf_artifact.path).exists():
            raise FileNotFoundError("PARSE_INPUT_NOT_FOUND")

        if method == "simple":
            text = self._parse_simple(Path(pdf_artifact.path))
        else:
            text = self._parse_ocr(Path(pdf_artifact.path))

        text_path = self.artifacts.text_path(paper_uid, method)
        info = self.artifacts.write_text(text_path, text)
        self.repo.upsert_artifact(
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "text",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": method,
                "parser_version": "v1",
            },
        )

        return {
            "paper_uid": paper_uid,
            "method": method,
            "text_path": str(info.path),
            "cached": False,
            "char_count": len(text),
        }

    def _parse_simple(self, pdf_path: Path) -> str:
        try:
            doc = fitz.open(str(pdf_path))
            texts = [page.get_text() for page in doc]
            doc.close()
            text = "\n\n".join(t.strip() for t in texts if t)
            if not text.strip():
                raise RuntimeError("PARSE_EXEC_FAILED")
            return text
        except Exception:
            logger.exception("Simple parse failed for pdf=%s", pdf_path)
            raise

    def _parse_ocr(self, pdf_path: Path) -> str:
        ocr_url = self._ocr_url()
        if not ocr_url:
            raise RuntimeError("PARSE_EXEC_FAILED")
        timeout = self.repo.ensure_profile().ocr_timeout_seconds
        with pdf_path.open("rb") as f:
            try:
                response = requests.post(
                    ocr_url,
                    files={"file": f},
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                text = payload.get("text", "")
                if not text:
                    raise RuntimeError("PARSE_EXEC_FAILED")
                return text
            except Exception:
                logger.exception("OCR parse failed for pdf=%s", pdf_path)
                raise

    @staticmethod
    def _ocr_url() -> Optional[str]:
        import os

        return os.getenv("OCR_SERVICE_URL")
