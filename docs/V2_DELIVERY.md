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
- `GET /api/v1/papers`
- `GET /api/v1/papers/{paper_uid}`
- `GET /api/v1/papers/{paper_uid}/pdf`
- `POST /api/v1/papers/import`
- `POST /api/v1/papers/{paper_uid}/parse`
- `POST /api/v1/papers/{paper_uid}/analyze`
- `POST /api/v1/recommendations/generate`
- `POST /api/v1/research/tasks`
- `GET /api/v1/research/tasks`
- `GET /api/v1/research/tasks/{task_id}/result`
- `POST /api/v1/reports/daily/generate`
- `POST /api/v1/reports/daily/generate-async`
- `GET /api/v1/reports/daily/{report_id}`
- `GET /api/v1/reports/daily/by-date/{report_date}`
- `GET /api/v1/sources/availability`
- `GET/PUT /api/v1/settings`
- `GET /api/v1/system/status`
- `GET /api/v1/tasks/{job_id}`

## 4. 已实现的关键规则
- 学术源支持 `arxiv` / `huggingface` / `openalex`
- 日报默认源为 `arxiv + huggingface`，默认时间窗口 `7` 天，默认 arXiv AI 分区：
  - `cs.AI, cs.LG, cs.CL, cs.CV, cs.RO, stat.ML`
- 日报前端走异步任务：创建任务后轮询 `job` 状态，不依赖前端超时等待
- 源可用性检查以“真实数据”为标准（不是仅 API 不报错）：
  - 通过 `GET /api/v1/sources/availability` 统一检查
  - 若源网络不可达/无真实论文数据，标记为不可用
- 缺失 PDF 允许保留元信息并低权重参与推荐
- 下载 / 解析 / 分析采用懒加载：
  - 获取论文仅拉取元信息；
  - 在访问 PDF、解析、分析、日报富化等场景按需触发下载/解析/分析；
  - 在调用解析/分析前会先保证 PDF 可用（或直接命中文本缓存）；
  - 单篇懒加载失败不会导致日报整体失败。
- 推荐融合默认五策略等权（含被推荐次数反向策略）
- 推荐新增“被推荐次数反向”策略：被推荐次数越高，排序得分越低
- 解析失败即失败，OCR 不重试
- 调研任务独立 workdir，任务结束即清理，清理失败异步重试
- `sources.json` 最小协议：`title,url,source,published_at,evidence_snippet`
- `evidence_snippet` 最大 300 字符
- 设置保存后即时生效（只作用于新任务）
- 不做设置变更审计

## 5. 注意事项
- 默认研究任务会调用 `claude` CLI；测试环境可设置 `V2_RESEARCH_FAKE=1`。
- 论文源可用性以“真实数据可获取”为准，不再使用本地兜底样本伪造成功。
- 日志默认输出到标准输出，错误路径使用 traceback（`logger.exception`）；可通过 `V2_LOG_LEVEL` 调整日志级别。

## 6. 前端交付
- 前端工程目录：`frontend/`
- 页面：论文日报、论文探索、深度调研、设置
- 布局：左侧导航 + 右侧子页面
- 组件库：Ant Design

## 7. 旧代码与旧数据清理
- 已移除旧实现目录：`backend/`、`daily_paper/`、`tests/`
- 已移除旧数据目录/文件：`data/papers/`、`data/text/`、`data/logs/`、`data/papers.db`
- 当前仓库仅保留 V2 实现与 V2 数据资产（`v2/`、`tests_v2/`、`frontend/`、`data/v2_*`）
