#!/usr/bin/env bash
set -euo pipefail

export V2_DATABASE_URL="${V2_DATABASE_URL:-sqlite:///data/v2_daily_paper.db}"
export V2_ARTIFACT_ROOT="${V2_ARTIFACT_ROOT:-data/v2_artifacts}"
export V2_RESEARCH_ROOT="${V2_RESEARCH_ROOT:-data/research_runs}"

python -m uvicorn v2.api.app:app --host "${V2_API_HOST:-127.0.0.1}" --port "${V2_API_PORT:-8001}" --reload
