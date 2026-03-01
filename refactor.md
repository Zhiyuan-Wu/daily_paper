# Daily Paper 重构计划（V7）

## 0.6 完成度核验与清理记录（2026-03-01）

### 完成度核验结论
1. 新架构五层已落地：`v2/contracts`、`v2/foundation`、`v2/db`、`v2/services`、`v2/api`、`frontend`。
2. 服务层六个无状态微服务实现已完成：`fetch`、`parse`、`analyze`、`recommend`、`research`、`daily_report`。
3. API 层、SQLite 数据模型、前端页面与任务流均已联通。
4. 启动脚本 `start_server.sh` 支持前后端一键启动且端口可配置。
5. 关键测试基线通过：`tests_v2` 通过，端到端主链路可运行。

### 旧资产清理结论
1. 已移除旧代码目录：`backend/`、`daily_paper/`、`tests/`。
2. 已移除旧数据目录/文件：`data/papers/`、`data/text/`、`data/logs/`、`data/papers.db`。
3. 保留 V2 数据与运行资产：`data/v2_daily_paper.db`、`data/v2_artifacts/`、`data/research_runs/`。

## 0. 细节确认（已锁定）

本节为你已确认的架构决策，后续实现默认按此执行。

1. `Q1`：单用户本地应用（`B`）。
2. `Q2`：先单机多进程部署（`A`）。
3. `Q3`：学术检索源采用可配置适配器，默认关闭（`A`）。
4. `Q4`：解析不做自动回退；只执行用户指定方法，默认 `simple`，失败即失败。
5. `Q5`：分析服务采用单一 pipeline（`B`）。
6. `Q6`：推荐目标优先显式反馈；融合权重可配置，默认等权。
7. `Q7`：深度调研只使用 Claude Code CLI。
8. `Q8`：不做自动触发/调度，全部手动触发（`B`）。
9. `Q9`：日期按用户时区，默认 `Asia/Shanghai`（`A`）。
10. `Q10`：前端使用 React 技术栈（`A`）。
11. `Q11`：不做鉴权设计，本地免登录（`B`）。
12. `Q12`：本地 PDF 文件管理采用 LRU。
13. `Q13`：服务间通信采用 HTTP/JSON（`A`）。
14. `Q14`：异步任务先用 SQLite jobs + worker 轮询（`A`）。
15. `Q15`：保留可追溯信息（输入摘要/版本/耗时/错误）（`A`）。

## 0.1 追加确认（R1-R12，已锁定）

1. `R1`：学术检索源使用稳定第三方 API，不做网页抓取。
2. `R2`：解析首期仅支持 `simple`、`ocr`。
3. `R3`：沿用现有本地 OCR 服务。
4. `R4`：推荐首批策略包含 `llm_theme`。
5. `R5`：融合权重仅维护全局默认值（设置页配置）。
6. `R6`：PDF LRU 采用双阈值（磁盘占用 + 文件数量）。
7. `R7`：LRU 不设保底，严格按规则淘汰。
8. `R8`：Claude 任务固定输出 `report.md` + `sources.json`。
9. `R9`：调研报告语言固定中文。
10. `R10`：前端组件库锁定 `Ant Design`。
11. `R11`：API 错误格式统一 `{code, message, details, trace_id}`。
12. `R12`：测试基线为“每服务至少 1 个集成测试 + API 编排 E2E”。

## 0.2 参数确认（U1-U8，已锁定）

1. `U1`：学术检索 API 供应商为 `OpenAlex`。
2. `U2`：PDF LRU 默认阈值为 `10GB` + `5000` 文件，且阈值可配置。
3. `U3`：OCR 调用失败不重试，直接失败返回。
4. `U4`：批处理默认并发为下载 `4`、解析 `2`、分析 `2`，且并发可配置。
5. `U5`：Claude 调研任务默认超时 `45` 分钟，且超时可配置。
6. `U6`：推荐默认全局权重等权（四策略均为 `0.25`）。
7. `U7`：调研报告使用固定 6 段模板。
8. `U8`：所有服务端口均从 `.env` 读取。

## 0.3 规则确认（N1-N7，已锁定）

1. `N1`：OpenAlex 缺少可下载 PDF 时保留元信息，标记 `pdf_unavailable`，仍可参与推荐但低权重。
2. `N2`：OpenAlex 首期仅检索 `works`。
3. `N3`：OCR 默认超时 `120s`。
4. `N4`：日报流程任一步骤失败则整任务失败，不输出降级日报。
5. `N5`：分析与日报的 LLM Provider 沿用当前项目 `.env` 配置。
6. `N6`：Claude Code 每次任务使用独立临时工作目录。
7. `N7`：OpenAlex 默认限流 `2 req/s`。

## 0.4 细化确认（M1-M5，已锁定）

1. `M1`：OpenAlex 无 PDF 时不做 Unpaywall 等额外回退，仅使用 OpenAlex 提供链接。
2. `M2`：多源去重主键优先 `DOI`，缺失时回退 `title+first_author+year`。
3. `M3`：Claude 临时工作目录在任务完成后立即清理，仅保留落库结果。
4. `M4`：`sources.json` 最小字段为 `title`, `url`, `source`, `published_at`, `evidence_snippet`。
5. `M5`：前端设置页参数保存后立即生效（影响后续新任务）。

## 0.5 收尾确认（P1-P5，已锁定）

1. `P1`：无 PDF 论文在前端列表中展示并标记“无PDF”，详情页可查看元信息与摘要。
2. `P2`：归并冲突自动处理并记录冲突日志，不引入人工确认队列。
3. `P3`：临时目录清理失败仅告警并异步重试，不影响任务成功状态。
4. `P4`：`sources.json.evidence_snippet` 长度上限为 `300` 字符。
5. `P5`：不做设置变更审计。

## 1. 设计原则（详细）

## 1.1 分层原则
1. 数据层只处理持久化，不承载业务规则。
2. 服务层只处理业务逻辑，不直接读写 API 层数据库。
3. API 层只做编排、聚合和落库，不做算法实现。
4. 前端只负责展示和交互，不嵌入复杂业务决策。

## 1.2 无状态服务原则
1. 服务进程不保存会话状态。
2. 所有任务状态写入 SQLite `jobs` 表。
3. 文件状态由 Artifact Manager 管理。
4. 失败恢复依赖幂等请求 + 任务重试，而非进程内内存状态。

## 1.3 契约优先原则
1. 每个服务对外暴露版本化接口：`/v1/...`。
2. 请求与响应使用统一 schema（Pydantic）。
3. 错误响应统一：`code`, `message`, `details`, `trace_id`。

## 1.4 可追溯原则
1. API 层记录每次服务调用的输入摘要（脱敏）、输出摘要、耗时、版本。
2. 所有任务均关联 `trace_id`。
3. 调研与日报结果必须可反查来源论文与生成参数。

## 1.5 本地优先原则
1. 单用户、免登录、离线可运行优先。
2. 不引入 Redis、消息队列、K8s 等额外基础设施。
3. 后续扩展点保留，但当前不超前设计。

## 2. 新架构总览

## 2.1 目标分层
- 数据层：SQLite + Alembic。
- 基础工具层：contracts、plugin-runtime、artifact-manager、llm-kit、observability。
- 服务层：`svc-fetch`、`svc-parse`、`svc-analyze`、`svc-recommend`、`svc-research`、`svc-daily-report`。
- API 层：本地 BFF 与任务编排。
- 前端：React 单页应用。

## 2.2 部署拓扑（单机多进程）
1. `api`：统一对前端暴露接口。
2. `worker`：执行异步 jobs。
3. `svc-fetch`：论文获取服务。
4. `svc-parse`：论文解析服务。
5. `svc-analyze`：论文分析服务。
6. `svc-recommend`：推荐服务。
7. `svc-research`：深度调研服务。
8. `svc-daily-report`：日报服务。

端口配置：全部通过 `.env` 注入（如 `API_PORT`, `FETCH_SERVICE_PORT` 等），不在代码中硬编码。

## 2.3 通信模式
1. 服务间全部 HTTP/JSON。
2. 短流程同步请求，长流程提交 jobs 异步执行。
3. 异步任务返回 `202 + task_id`，前端轮询状态。

## 3. 服务层详细设计

## 3.1 论文获取服务 `svc-fetch`

### 职责边界
1. 插件化搜索论文（arXiv、Hugging Face、OpenAlex）。
2. 下载论文 PDF。
3. 使用 Artifact Manager 做路径分配、去重、哈希登记。

### 不负责
1. 不写业务表。
2. 不做推荐与用户逻辑。

### 插件约定
```python
class SourcePlugin(Protocol):
    source_name: str
    def search(self, query: SearchQuery) -> list[SourcePaper]: ...
    def download(self, external_id: str, target: Path) -> DownloadOutput: ...
```

### 已确认实现
1. 学术检索源通过 OpenAlex API 适配器接入。
2. OpenAlex 插件可通过配置启停并设置限流参数（默认 `2 req/s`）。
3. 首期仅检索 OpenAlex `works` 资源。
4. 当记录无可下载 PDF 时，保留元信息并标记 `pdf_unavailable`。
5. 不做 OpenAlex 之外的 PDF 回退抓取。

### 接口契约
1. `POST /v1/search`
   - 入参：`sources[]`, `keywords[]`, `start_date`, `end_date`, `page`, `page_size`
   - 出参：`items[]`（`source`, `external_id`, `title`, `authors[]`, `abstract`, `published_at`, `url`, `pdf_url`）
2. `POST /v1/download`
   - 入参：`source`, `external_id`
   - 出参：`paper_uid`, `pdf_artifact`, `deduplicated`
3. `POST /v1/download/batch`
   - 入参：`requests[]`
   - 出参：`task_id`

### 关键用例
1. 指定源+日期检索论文。
2. 批量下载并自动去重。
3. 下载失败可重试，不覆盖现有文件。

### 多源去重规则（已确认）
1. 优先按 `DOI` 做跨源归并。
2. 无 `DOI` 时按 `title+first_author+year` 做近似归并。
3. 归并后保留来源映射，避免丢失原始 source/external_id。
4. 归并冲突自动处理并写冲突日志，不引入人工确认流程。

## 3.2 论文解析服务 `svc-parse`

### 职责边界
1. 输入 `paper_uid` 或 `pdf_path` + `method` 执行解析。
2. 仅执行指定解析方法，不自动回退。
3. 解析结果按 `(paper_uid, method, parser_version)` 缓存。

### 已确认行为
1. 默认 `method = simple`。
2. 用户指定 `ocr` 就只走 `ocr`。
3. 解析异常直接返回失败，不自动切换其他方法。
4. 首批仅支持 `simple` 与 `ocr` 两种方法。
5. OCR 失败不做自动重试，直接返回错误码。

### 接口契约
1. `POST /v1/parse`
   - 入参：`paper_uid | pdf_path`, `method`, `force_reparse`
   - 出参：`text_artifact`, `method`, `cached`, `char_count`
2. `POST /v1/parse/batch`
   - 入参：`items[]`, `method`
   - 出参：`task_id`
3. `GET /v1/parse/{paper_uid}`
   - 入参：`method`, `parser_version`
   - 出参：已存在解析结果元数据

### 错误码
- `PARSE_METHOD_UNSUPPORTED`
- `PARSE_INPUT_NOT_FOUND`
- `PARSE_EXEC_FAILED`

## 3.3 论文分析服务 `svc-analyze`

### 职责边界
1. 输入元信息 + 全文文本。
2. 执行单一 pipeline。
3. 输出结构化结果供推荐/日报复用。

### 单 pipeline 输出结构
- `tldr`
- `key_points[]`
- `problem_statement`
- `method_summary`
- `experiment_summary`
- `limitations`
- `tags[]`

### 模型配置（已确认）
1. 分析服务 LLM Provider 直接沿用当前项目 `.env` 配置，不新增独立 Provider。

### 接口契约
1. `POST /v1/analyze`
   - 入参：`paper_meta`, `full_text`
   - 出参：`analysis_json`
2. `POST /v1/analyze/batch`
   - 入参：`items[]`
   - 出参：`task_id`

## 3.4 推荐算法服务 `svc-recommend`

### 职责边界
1. 多召回插件打分。
2. 融合策略输出最终排序。
3. 分数归一化到 `[0, 1]`。

### 融合策略（已确认）
1. 每个策略输出归一分 `s_i ∈ [0,1]`。
2. 最终分：`score = Σ(w_i * s_i) / Σ(w_i)`。
3. 默认 `w_i` 等权重（四策略均 `0.25`）。
4. 权重仅由设置页维护全局默认值，推荐请求不做临时覆盖。

### 接口契约
1. `POST /v1/recommend`
   - 入参：`papers[]`, `query_context`, `top_k`
   - 出参：`items[]`（`paper_uid`, `score`, `rank`, `strategy_breakdown`, `reasons[]`）
2. `GET /v1/plugins`
3. `POST /v1/evaluate`

### 查询上下文（显式反馈优先）
- `liked_papers[]`
- `disliked_papers[]`
- `read_papers[]`
- `interest_keywords[]`
- `excluded_keywords[]`

### 缺失 PDF 处理（已确认）
1. `pdf_unavailable=true` 的论文默认加入惩罚系数（低权重）后再参与融合。
2. 该惩罚系数为全局配置项，默认开启。

### 首批策略集合（已确认）
1. `keyword_semantic`
2. `interested_semantic`
3. `repetition_penalty`
4. `llm_theme`

## 3.5 深度调研服务 `svc-research`

### 职责边界
1. 根据 topic 组装调研任务。
2. 调用 Claude Code CLI 执行。
3. 回收产出报告并返回。

### 执行方式（已确认）
固定命令模式：
```bash
cd /path/to/task_workdir && claude 'Read /absolute/path/to/task_xxx.txt for work details.' --allowedTools 'Bash,Read,Edit,Write,WebFetch'
```

### 输出协议（已确认）
1. 固定输出文件：`report.md`、`sources.json`。
2. 报告语言固定中文。
3. 报告采用固定 6 段结构：背景、问题拆解、方法对比、关键文献、结论、后续行动。
4. `sources.json` 最小字段：`title`, `url`, `source`, `published_at`, `evidence_snippet`。
5. `evidence_snippet` 上限 `300` 字符。

### 内部步骤
1. 为任务创建独立临时工作目录（例如 `data/research_runs/{task_id}/`）。
2. 在临时目录生成 `task_xxx.txt`（包含 skill 指令、调研主题、输出要求）。
3. 切换到该目录调用 CLI。
4. 轮询子进程完成状态（默认超时 45 分钟，可配置）。
5. 读取 `report.md` 与 `sources.json`。
6. 写入 research 结果表。
7. 任务完成后立即清理临时 `workdir`。
8. 清理失败时记录告警并异步重试，不回滚任务成功状态。

### 接口契约
1. `POST /v1/research/tasks`
   - 入参：`topic`, `constraints`
   - 出参：`task_id`
2. `GET /v1/research/tasks/{task_id}`
3. `GET /v1/research/tasks/{task_id}/result`

## 3.6 日报生成服务 `svc-daily-report`

### 职责边界
1. 手动触发日报任务。
2. 顺序编排：获取 -> 解析 -> 分析 -> 推荐 -> 总结。
3. 输出日报文档与推荐条目。

### 已确认行为
1. 无自动调度。
2. 报告日期按用户时区计算（默认 `Asia/Shanghai`）。
3. 任一步骤失败则整任务失败，不输出降级日报。
4. 日报总结 LLM Provider 沿用当前项目 `.env` 配置。

### 接口契约
1. `POST /v1/daily-report/tasks`
   - 入参：`report_date`, `sources[]`, `keywords[]`, `top_k`
   - 出参：`task_id`
2. `GET /v1/daily-report/tasks/{task_id}`
3. `GET /v1/daily-report/{report_id}`

## 4. API 层设计

## 4.1 定位
1. 本地 BFF（无鉴权）。
2. 聚合前端请求并调用各服务。
3. 落库业务数据与任务状态。

## 4.2 接口分组（`/api/v1`）
1. `papers`：搜索、导入、详情、解析、分析。
2. `recommendations`：生成推荐、历史推荐、反馈提交。
3. `research`：创建任务、状态查询、结果获取。
4. `reports`：创建日报任务、查看日报。
5. `settings`：本地配置（时区、默认源、策略权重、并发、LRU 阈值、超时参数）。
6. `tasks`：统一任务查询。

设置生效策略：配置保存后立即生效，仅影响“新提交任务”；运行中任务不热更新。

## 4.3 幂等与失败处理
1. 支持 `Idempotency-Key`。
2. 写操作先创建 job，再执行实际调用。
3. 服务调用失败记录 `error_code`, `error_message`, `retryable`。
4. 统一错误响应结构：`{code, message, details, trace_id}`。

## 5. SQLite 数据模型（单用户版）

> 不兼容旧表，直接重建。

## 5.1 核心表

### `app_profile`
- `id` INTEGER PK CHECK(id=1)
- `timezone` TEXT DEFAULT `Asia/Shanghai`
- `interest_keywords_json` TEXT
- `excluded_keywords_json` TEXT
- `default_sources_json` TEXT
- `recommend_strategy_weights_json` TEXT
- `scholar_provider` TEXT DEFAULT `openalex`
- `scholar_rate_limit_rps` REAL
- `batch_download_concurrency` INTEGER
- `batch_parse_concurrency` INTEGER
- `batch_analyze_concurrency` INTEGER
- `pdf_lru_max_bytes` INTEGER
- `pdf_lru_max_count` INTEGER
- `ocr_timeout_seconds` INTEGER
- `research_timeout_minutes` INTEGER
- `updated_at` DATETIME

### `papers`
- `paper_uid` TEXT PK
- `source` TEXT
- `external_id` TEXT
- `doi` TEXT NULL
- `title` TEXT
- `authors_json` TEXT
- `abstract` TEXT
- `published_at` DATETIME
- `source_url` TEXT
- `pdf_unavailable` BOOLEAN DEFAULT 0
- `created_at` DATETIME
- UNIQUE(`source`, `external_id`)

### `paper_source_links`
- `id` TEXT PK
- `paper_uid` TEXT FK
- `source` TEXT
- `external_id` TEXT
- `doi` TEXT NULL
- `source_url` TEXT
- `created_at` DATETIME
- UNIQUE(`source`, `external_id`)

### `paper_artifacts`
- `id` TEXT PK
- `paper_uid` TEXT FK
- `artifact_type` TEXT (`pdf|text|analysis`)
- `path` TEXT
- `file_hash` TEXT
- `size_bytes` INTEGER
- `last_accessed_at` DATETIME
- `created_at` DATETIME
- `parser_method` TEXT NULL
- `parser_version` TEXT NULL
- INDEX(`artifact_type`, `last_accessed_at`)

### `paper_analysis`
- `id` TEXT PK
- `paper_uid` TEXT FK
- `pipeline_version` TEXT
- `analysis_json` TEXT
- `created_at` DATETIME

### `paper_feedback`
- `id` TEXT PK
- `paper_uid` TEXT FK
- `action` TEXT (`like|dislike|read|save|dismiss`)
- `note` TEXT NULL
- `created_at` DATETIME
- INDEX(`created_at`)

### `recommendation_runs`
- `id` TEXT PK
- `query_context_json` TEXT
- `strategy_weights_json` TEXT
- `created_at` DATETIME

### `recommendation_items`
- `id` TEXT PK
- `run_id` TEXT FK
- `paper_uid` TEXT FK
- `score` REAL
- `rank` INTEGER
- `strategy_breakdown_json` TEXT
- `reasons_json` TEXT
- INDEX(`run_id`, `rank`)

### `daily_reports`
- `id` TEXT PK
- `report_date` DATE
- `timezone` TEXT
- `summary_md` TEXT
- `meta_json` TEXT
- `created_at` DATETIME
- UNIQUE(`report_date`, `timezone`)

### `daily_report_items`
- `id` TEXT PK
- `report_id` TEXT FK
- `paper_uid` TEXT FK
- `recommend_score` REAL
- `rank` INTEGER
- `analysis_snapshot_json` TEXT

### `research_tasks`
- `id` TEXT PK
- `topic` TEXT
- `constraints_json` TEXT
- `status` TEXT (`pending|running|failed|completed`)
- `workdir_path` TEXT
- `task_file_path` TEXT
- `report_file_path` TEXT NULL
- `started_at` DATETIME NULL
- `finished_at` DATETIME NULL
- `error_message` TEXT NULL

### `research_reports`
- `id` TEXT PK
- `task_id` TEXT FK
- `report_md` TEXT
- `sources_json` TEXT
- `created_at` DATETIME

### `jobs`
- `id` TEXT PK
- `job_type` TEXT
- `payload_json` TEXT
- `status` TEXT (`pending|running|failed|completed`)
- `progress` INTEGER
- `result_ref` TEXT NULL
- `error_code` TEXT NULL
- `error_message` TEXT NULL
- `trace_id` TEXT
- `created_at` DATETIME
- `updated_at` DATETIME
- INDEX(`status`, `created_at`)

### `service_call_logs`
- `id` TEXT PK
- `trace_id` TEXT
- `service_name` TEXT
- `endpoint` TEXT
- `request_summary_json` TEXT
- `response_summary_json` TEXT
- `status_code` INTEGER
- `duration_ms` INTEGER
- `error_code` TEXT NULL
- `created_at` DATETIME

## 5.2 PDF LRU 策略（已确认）

### 触发条件
1. 每次下载后检查 PDF 总占用与文件数量。
2. 每次 worker 周期性检查（可配置）。
3. 任一阈值超限即触发淘汰（双阈值 OR）。

### 淘汰规则
1. 仅淘汰 `artifact_type=pdf`。
2. 按 `last_accessed_at` 升序淘汰最久未使用文件。
3. 保留 `text` 与 `analysis` 结果，不随 PDF 一起删除。
4. 不设“保底保留 N 篇”，严格按 LRU + 阈值执行淘汰。
5. 被淘汰后在 `paper_artifacts` 标记为 `evicted`（或软删记录）。

## 5.3 关键默认参数（已确认）
1. 学术源提供方：`openalex`。
2. OpenAlex 限流：默认 `2 req/s`。
3. OpenAlex 范围：首期仅 `works`。
4. OpenAlex 无 PDF 时不做外部回退，只标记 `pdf_unavailable`。
5. LRU 阈值：`10GB`、`5000` 文件（双阈值）。
6. OCR 超时：默认 `120s`；重试次数固定 `0`。
7. 批处理并发：下载 `4`、解析 `2`、分析 `2`。
8. 调研任务超时：`45` 分钟。
9. 推荐策略权重：`keyword_semantic=0.25`、`interested_semantic=0.25`、`repetition_penalty=0.25`、`llm_theme=0.25`。
10. 调研任务完成后立即清理 `workdir`。
11. 临时目录清理失败仅告警并异步重试，不影响任务成功状态。
12. 设置保存后立即生效（影响后续新任务）。
13. 不做设置变更审计。
14. 上述参数均通过 `settings` 和 `.env` 允许覆盖。

## 6. 前端设计（React）

## 6.1 技术栈
1. `React + TypeScript + Vite`
2. `React Router`
3. `TanStack Query`
4. `Zustand`
5. `React Hook Form + Zod`
6. `Ant Design`

## 6.2 页面与流程
1. 论文探索页：检索、导入、批量操作；无 PDF 论文显示“无PDF”标签。
2. 论文详情页：元信息、解析文本、分析结果、反馈动作。
3. 推荐页：推荐结果、原因解释、策略分解。
4. 深度调研页：输入主题、查看任务状态、查看报告。
5. 日报页：手动触发日报、查看历史日报。
6. 任务中心：统一任务进度与错误排查。
7. 设置页：时区、默认源、策略默认权重。

## 7. 改动计划（详细）

## 7.1 目录重构目标
```text
.
├── packages/
│   ├── contracts/
│   ├── plugin-runtime/
│   ├── artifact-manager/
│   └── observability/
├── services/
│   ├── fetch-service/
│   ├── parse-service/
│   ├── analyze-service/
│   ├── recommend-service/
│   ├── research-service/
│   └── daily-report-service/
├── api/
│   ├── app/
│   ├── repositories/
│   ├── orchestrators/
│   └── migrations/
├── frontend/
└── data/
```

## 7.2 现有代码到新架构映射
1. `daily_paper/downloaders/*` -> `services/fetch-service/plugins/*`
2. `daily_paper/parsers/pdf_parser.py` -> `services/parse-service/parsers/simple.py`、`ocr.py`
3. `daily_paper/recommenders/*` -> `services/recommend-service/strategies/*`
4. `daily_paper/reports/generator.py` -> `services/daily-report-service/core/*`
5. `backend/routers/*` -> `api/app/routers/*`（仅保留编排）
6. `backend/static/frontend/*` -> `frontend/src/*`（全量替换）

## 7.3 分阶段执行

### 阶段 A：基线与契约（3-4 天）
1. 初始化 `packages/contracts`。
2. 定义统一错误码与任务状态。
3. 建立 `service_call_logs` 追踪规范。

### 阶段 B：数据层重建（2-3 天）
1. 编写 SQLite 新 schema。
2. Alembic 初始迁移。
3. 仓储层（repositories）实现。

### 阶段 C：fetch + parse 服务（5-7 天）
1. 抽离 fetch 插件体系。
2. 接入 OpenAlex 适配器（按配置启停）。
3. 实现 parse 指定方法执行（无自动回退，OCR 不重试）。
4. 打通 artifact 去重与缓存。
5. 加入 PDF LRU 回收逻辑（双阈值可配置）。

### 阶段 D：analyze + recommend 服务（4-6 天）
1. 单 pipeline 分析服务落地。
2. 推荐策略（含 `llm_theme`）+ 全局权重配置（默认等权）。
3. 输出可解释 breakdown。

### 阶段 E：research + daily-report 服务（4-6 天）
1. Claude Code CLI 调研执行器。
2. 固定 6 段调研模板与输出协议（`report.md` + `sources.json`）。
3. 日报手动编排链路。
4. 报告落库与展示接口。

### 阶段 F：API/BFF 重组（3-4 天）
1. 路由重写为编排层。
2. jobs + worker 轮询执行。
3. 统一错误与 trace_id。
4. 端口与并发/超时参数全部转为 `.env` + settings 可配置。

### 阶段 G：前端重写（5-8 天）
1. React 工程初始化。
2. 核心页面开发（探索、详情、推荐、调研、日报、任务）。
3. 联调与体验修正。

### 阶段 H：测试与切换（3-4 天）
1. 每个服务至少 1 个集成测试 + API 编排 E2E。
2. 本地运行脚本与文档。
3. 切换到新系统（不迁移旧数据）。

## 8. 验收标准
1. 6 个服务均可独立启动并健康检查通过。
2. API 层无算法实现代码，只做编排与落库。
3. 解析严格按指定方法执行，失败即失败。
4. 推荐融合权重可配置且默认等权。
5. 深度调研只通过 Claude Code CLI 完成。
6. 日报仅手动触发，按时区计算日期。
7. PDF LRU 生效且不会删除 text/analysis 结果。
8. 所有服务调用均可追溯。
9. API 错误格式统一 `{code, message, details, trace_id}`。
10. 调研任务稳定产出 `report.md` + `sources.json`。

## 9. 风险与缓解
1. OpenAlex API 限流与可用性波动。
   - 缓解：限流器 + 本地缓存 + 失败降级不影响其他数据源。
2. OCR 质量与成本波动。
   - 缓解：显式由用户选 method，失败即返回；通过任务重提实现人工重试。
3. Claude CLI 任务输出不稳定。
   - 缓解：固定 6 段模板 + 输出文件协议 + 结果校验 + 超时控制。
4. 本地磁盘占用增长。
   - 缓解：PDF LRU + 占用监控。

## 10. 下一步（执行顺序）
1. 先冻结 contracts 与 SQLite schema。
2. 优先落地 `fetch/parse` + Artifact + LRU。
3. 再落地 `recommend`（可配置权重）和 `research`（Claude CLI）。
4. 最后完成日报编排与前端替换。

## 11. 可开工任务清单（模块级 + 文件级）

## 11.1 contracts 包
1. 新建 `packages/contracts/common.py`：统一错误响应、分页、任务状态 schema。
2. 新建 `packages/contracts/fetch.py`：搜索/下载请求响应模型。
3. 新建 `packages/contracts/parse.py`：解析请求响应模型与错误码。
4. 新建 `packages/contracts/analyze.py`：分析输入输出模型。
5. 新建 `packages/contracts/recommend.py`：推荐输入、融合结果、权重模型。
6. 新建 `packages/contracts/research.py`：调研任务、结果、sources 模型。
7. 新建 `packages/contracts/report.py`：日报任务与结果模型。

## 11.2 artifact-manager 包
1. 新建 `packages/artifact-manager/manager.py`：路径分配、哈希登记、访问时间更新。
2. 新建 `packages/artifact-manager/lru.py`：双阈值 LRU 回收实现。
3. 新建 `packages/artifact-manager/models.py`：artifact 元数据对象。

## 11.3 fetch-service
1. 新建 `services/fetch-service/app/main.py`：服务入口与路由注册。
2. 新建 `services/fetch-service/app/routers/fetch.py`：`/v1/search`、`/v1/download`、`/v1/download/batch`。
3. 新建 `services/fetch-service/app/plugins/openalex.py`：OpenAlex `works` 适配器（2 req/s 默认限流）。
4. 新建 `services/fetch-service/app/plugins/arxiv.py` 与 `huggingface.py`：现有逻辑迁移。
5. 新建 `services/fetch-service/app/core/service.py`：插件调度与 `pdf_unavailable` 标记（不做 Unpaywall 回退）。
6. 新建 `services/fetch-service/app/core/dedup.py`：`DOI` 优先、`title+first_author+year` 回退归并。
7. 新建 `services/fetch-service/app/core/conflict_log.py`：归并冲突日志记录。

## 11.4 parse-service
1. 新建 `services/parse-service/app/main.py`。
2. 新建 `services/parse-service/app/parsers/simple.py`。
3. 新建 `services/parse-service/app/parsers/ocr.py`（`timeout=120s`，`retry=0`）。
4. 新建 `services/parse-service/app/core/service.py`：指定 method 执行与缓存命中。

## 11.5 analyze-service
1. 新建 `services/analyze-service/app/main.py`。
2. 新建 `services/analyze-service/app/core/pipeline.py`：单 pipeline 实现。
3. 新建 `services/analyze-service/app/core/llm_client.py`：沿用 `.env` Provider 配置。

## 11.6 recommend-service
1. 新建 `services/recommend-service/app/main.py`。
2. 新建 `services/recommend-service/app/strategies/*.py`：四个首批策略。
3. 新建 `services/recommend-service/app/core/fusion.py`：全局权重融合。
4. 新建 `services/recommend-service/app/core/post_filter.py`：`pdf_unavailable` 惩罚系数。

## 11.7 research-service
1. 新建 `services/research-service/app/main.py`。
2. 新建 `services/research-service/app/core/task_builder.py`：固定 6 段模板生成。
3. 新建 `services/research-service/app/core/executor.py`：每任务独立 `workdir` 调用 Claude CLI。
4. 新建 `services/research-service/app/core/result_reader.py`：读取 `report.md` + `sources.json`（最小字段协议校验）。
5. 新建 `services/research-service/app/core/cleanup.py`：任务完成立即清理 `workdir`。
6. 新建 `services/research-service/app/core/cleanup_retry.py`：清理失败异步重试。

## 11.8 daily-report-service
1. 新建 `services/daily-report-service/app/main.py`。
2. 新建 `services/daily-report-service/app/core/pipeline.py`：获取->解析->分析->推荐->总结。
3. 新建 `services/daily-report-service/app/core/fail_policy.py`：任一步骤失败即任务失败。

## 11.9 API 层
1. 新建 `api/app/main.py`：BFF 入口。
2. 新建 `api/app/routers/papers.py`、`recommendations.py`、`research.py`、`reports.py`、`tasks.py`、`settings.py`。
3. 新建 `api/app/orchestrators/*.py`：跨服务调用编排。
4. 新建 `api/app/repositories/*.py`：SQLite 仓储。
5. 新建 `api/app/services/settings_runtime.py`：设置项即时生效（仅新任务）。
6. 新建 `api/migrations/versions/0001_init_schema.py`：V6 schema 初始化。

## 11.10 worker
1. 新建 `api/app/worker/runner.py`：jobs 轮询与执行。
2. 新建 `api/app/worker/handlers/*.py`：批下载、批解析、调研、日报 handler。

## 11.11 前端
1. 新建 `frontend/src/app/router.tsx`：路由。
2. 新建 `frontend/src/features/papers/*`：探索与详情页。
3. 新建 `frontend/src/features/recommendations/*`：结果页与解释视图。
4. 新建 `frontend/src/features/research/*`：任务提交、状态、报告页。
5. 新建 `frontend/src/features/reports/*`：日报页。
6. 新建 `frontend/src/features/settings/*`：全局参数配置页。
7. 新建 `frontend/src/shared/api/client.ts`：统一请求层与错误处理。
8. 新建 `frontend/src/shared/components/PdfAvailabilityTag.tsx`：无PDF标签组件。

## 11.12 测试
1. 新建 `tests/integration/test_fetch_service.py` 到 `test_daily_report_service.py`（每服务至少 1 个）。
2. 新建 `tests/e2e/test_api_orchestration.py`：API 编排主链路 E2E。
3. 新建 `tests/integration/test_lru_policy.py`：双阈值 LRU 行为验证。
