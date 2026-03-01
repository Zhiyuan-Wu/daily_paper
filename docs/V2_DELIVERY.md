# Daily Paper V2 交付说明

## 1. 交付内容
- 新分层实现：`v2/`
  - `v2/contracts`: 服务接口契约
  - `v2/foundation`: Artifact 管理与 LRU
  - `v2/db`: SQLite 新模型与仓储
  - `v2/services`: 六个服务（fetch/parse/analyze/recommend/research/daily_report）
  - `v2/api`: BFF API（端到端编排）
  - `v2/worker`: cleanup 重试 runner
- 启动脚本：`scripts/run_v2_api.sh`
- 测试：`tests_v2/`

## 2. 启动
```bash
./scripts/run_v2_api.sh
```

默认地址：`http://127.0.0.1:8001`

## 3. 关键 API
- `POST /api/v1/papers/search`
- `POST /api/v1/papers/import`
- `POST /api/v1/papers/{paper_uid}/parse`
- `POST /api/v1/papers/{paper_uid}/analyze`
- `POST /api/v1/recommendations/generate`
- `POST /api/v1/research/tasks`
- `GET /api/v1/research/tasks/{task_id}/result`
- `POST /api/v1/reports/daily/generate`
- `GET /api/v1/reports/daily/{report_id}`
- `GET/PUT /api/v1/settings`
- `GET /api/v1/tasks/{job_id}`

## 4. 已实现的关键规则
- OpenAlex 作为学术源，首期仅 `works`
- 缺失 PDF 允许保留元信息并低权重参与推荐
- 推荐融合默认四策略等权
- 解析失败即失败，OCR 不重试
- 调研任务独立 workdir，任务结束即清理，清理失败异步重试
- `sources.json` 最小协议：`title,url,source,published_at,evidence_snippet`
- `evidence_snippet` 最大 300 字符
- 设置保存后即时生效（只作用于新任务）
- 不做设置变更审计

## 5. 注意事项
- 默认研究任务会调用 `claude` CLI；测试环境可设置 `V2_RESEARCH_FAKE=1`。
- OpenAlex 网络不可用时，fetch 服务有本地兜底样本，保证开发可运行。

## 6. 前端交付
- 前端工程目录：`frontend/`
- 页面：探索、推荐、调研、日报、任务、设置
- 组件库：Ant Design

## 7. 旧代码与旧数据清理
- 已移除旧实现目录：`backend/`、`daily_paper/`、`tests/`
- 已移除旧数据目录/文件：`data/papers/`、`data/text/`、`data/logs/`、`data/papers.db`
- 当前仓库仅保留 V2 实现与 V2 数据资产（`v2/`、`tests_v2/`、`frontend/`、`data/v2_*`）
