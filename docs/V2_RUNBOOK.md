# V2 Runbook

## 一体化（推荐）
```bash
./scripts/run_v2_api.sh
```

API: `http://127.0.0.1:8001`

## 前后端一起启动（端口可配置）
```bash
./start_server.sh
```

常用环境变量：
- `BACKEND_APP`（默认 `v2.api.app:app`）
- `BACKEND_HOST`（默认 `0.0.0.0`）
- `BACKEND_PORT`（默认 `8001`）
- `FRONTEND_ENABLE`（默认 `1`，设为 `0` 可禁用前端）
- `FRONTEND_HOST`（默认 `0.0.0.0`）
- `FRONTEND_PORT`（默认 `5173`）
- `FRONTEND_INSTALL_DEPS`（默认 `1`，若无 `node_modules` 会先安装依赖）
- `V2_LOG_LEVEL`（默认 `INFO`，可设为 `DEBUG` 查看更详细日志）

示例：
```bash
BACKEND_PORT=9001 FRONTEND_PORT=5174 ./start_server.sh
```

## 六个服务独立启动（示例）
```bash
python -m uvicorn v2.services.fetch.app:app --host 127.0.0.1 --port 8101
python -m uvicorn v2.services.parse.app:app --host 127.0.0.1 --port 8102
python -m uvicorn v2.services.analyze.app:app --host 127.0.0.1 --port 8103
python -m uvicorn v2.services.recommend.app:app --host 127.0.0.1 --port 8104
python -m uvicorn v2.services.research.app:app --host 127.0.0.1 --port 8105
python -m uvicorn v2.services.daily_report.app:app --host 127.0.0.1 --port 8106
```

## 测试
```bash
pytest -q tests_v2
```

## 日志排障
- API 与服务错误路径会打印完整 traceback（`logger.exception`）。
- 生成日报报错可先查看：
  - `POST /api/v1/reports/daily/generate` 对应日志中的 `trace_id`
  - 同 `trace_id` 的 job 记录：`GET /api/v1/tasks/{job_id}`
- 异步日报推荐使用：
  - 创建任务：`POST /api/v1/reports/daily/generate-async`
  - 查询任务：`GET /api/v1/tasks/{job_id}`
- 调研任务同样为异步执行：
  - 创建任务：`POST /api/v1/research/tasks`
  - 查询任务：`GET /api/v1/research/tasks/{task_id}`
- 论文源真实可用性检查（非“仅 API 可访问”）：
  - `GET /api/v1/sources/availability?window_days=7`

## 研究任务本地测试模式
```bash
export V2_RESEARCH_FAKE=1
```
