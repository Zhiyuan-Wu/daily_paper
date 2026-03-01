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
- `BACKEND_PORT`（默认 `8011`）
- `FRONTEND_ENABLE`（默认 `1`，设为 `0` 可禁用前端）
- `FRONTEND_HOST`（默认 `0.0.0.0`）
- `FRONTEND_PORT`（默认 `5183`）
- `FRONTEND_INSTALL_DEPS`（默认 `1`，若无 `node_modules` 会先安装依赖）

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

## 研究任务本地测试模式
```bash
export V2_RESEARCH_FAKE=1
```
