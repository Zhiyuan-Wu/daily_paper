# Daily Paper V2 静态 Code Review 报告

## 1. 审查范围与方法
- 审查日期：2026-03-01
- 审查方式：静态代码审查（后端 `v2/`、前端 `frontend/src/`、测试 `tests_v2/`、脚本与文档）
- 辅助验证：
  - `pytest -q tests_v2`（结果：16 passed, 2 skipped）
  - `cd frontend && npm run build`（构建成功，产物过大告警）
- 重点维度：正确性、架构一致性、可扩展性、性能、规范、测试覆盖、实现/文档一致性

## 2. 总体结论
当前版本主流程可运行，但存在多项与总体设计原则冲突的高风险技术债。最关键问题集中在：
- 多源去重后的标识一致性破坏（会直接导致后续下载/解析失败）
- 会话与任务模型不符合并发/可靠性要求（全局 DB Session、进程内线程异步）
- 设置即时生效承诺与实现不一致（多项参数修改后不生效）
- 契约与文档承诺未完整落地（统一错误格式、服务调用日志、微服务边界）

## 3. 高优先级问题（Critical / High）

### C1. 多源去重破坏 `paper_uid` 不变量，导致下载/解析链路失效
- 位置：`v2/services/fetch/service.py:109`, `v2/services/fetch/service.py:118`, `v2/db/repo.py:32`, `v2/services/fetch/service.py:158`
- 问题：
  - 去重命中后将 `paper_uid` 改为已有论文 UID（正确方向），但仍用“新来源的 `source/external_id`”覆盖 `papers` 表主记录。
  - `download()` 又按 `source+external_id` 重新计算 UID，导致“行内 `paper_uid`”与“可推导 UID”不一致。
- 影响：
  - 同一论文跨源归并后，可能出现 PDF 下载到新 UID、而解析仍按旧 UID 查找，触发 `PARSE_INPUT_NOT_FOUND`。
  - 破坏去重后实体稳定性，造成隐蔽数据错配。
- 建议：
  - 将 `papers` 作为 canonical entity（`paper_uid` 稳定，不再覆盖 canonical `source/external_id`）。
  - 新来源仅写入 `paper_source_links`。
  - `download()` 改为先按 `(source, external_id)` 查 `paper_source_links` 映射到 canonical `paper_uid` 再处理。
  - 增加约束测试：跨源同 DOI 归并后，`paper_uid` 可用并可成功下载/解析/分析。

### C2. API/服务使用全局共享 SQLAlchemy Session，线程不安全
- 位置：`v2/api/app.py:48`, `v2/services/fetch/app.py:12`, `v2/services/parse/app.py:12`, `v2/services/analyze/app.py:12`, `v2/services/recommend/app.py:12`, `v2/services/research/app.py:12`, `v2/services/daily_report/app.py:14`, `v2/db/models.py:208`
- 问题：进程启动时创建单个 Session 并全局复用，未采用 per-request session 生命周期。
- 影响：
  - 并发请求下可能出现事务串扰、连接状态污染、难排查的一致性问题。
  - 与 FastAPI 常规最佳实践冲突，扩展性差。
- 建议：
  - `init_db()` 返回 `sessionmaker` 或 engine。
  - 在 FastAPI 依赖中按请求创建/关闭 session。
  - 后台线程/异步任务独立 session 并明确事务边界。

### C3. 异步任务模型不可靠：日报异步为进程内线程，研究任务为同步阻塞
- 位置：`v2/api/app.py:462`, `v2/api/app.py:467`, `v2/api/app.py:388`, `v2/api/app.py:392`, `v2/services/research/service.py:130`
- 问题：
  - 日报异步使用 `threading.Thread`，无持久队列、无重放机制。
  - 研究任务在 API 请求线程同步执行（可能长达 45 分钟）。
- 影响：
  - 进程重启/崩溃后任务丢失。
  - 请求超时风险高，无法支撑稳定长任务。
  - 与“jobs + worker”原则不一致。
- 建议：
  - 统一改为 job 入库 + 独立 worker 消费。
  - API 仅创建任务并返回 `202 + job_id`。
  - 增加任务 lease/重试/幂等语义。

### H1. “设置保存即时生效”未落实到多项关键参数
- 位置：`v2/api/settings_runtime.py:37`, `v2/api/app.py:47`, `v2/services/parse/service.py:92`, `v2/services/research/service.py:129`, `v2/services/fetch/service.py:30`, `v2/services/daily_report/service.py:85`, `v2/api/app.py:530`
- 问题：设置写入 DB，但多个服务实例持有启动时 `config` 快照，运行中不读取 profile。
- 影响：
  - `research_timeout_minutes`、`ocr_timeout_seconds`、`scholar_rate_limit_rps`、`timezone` 等修改后对新任务也可能不生效。
  - 与交付文档承诺冲突。
- 建议：
  - 关键运行参数统一从 `AppProfile` 按请求读取，或实现配置热加载机制。
  - `system/status` 与 report timezone 使用 profile 时区，不使用启动静态配置。

### H2. `papers/search` 失败时 job 可能永远停留 `pending`
- 位置：`v2/api/app.py:203`
- 问题：该端点创建 job 后无异常捕获与失败状态回写。
- 影响：任务追踪误导、排障困难。
- 建议：参照其他端点补全 try/except，失败时 `update_job(status="failed", ...)`。

### H3. 服务健康检查逻辑与实现不匹配，状态长期误报
- 位置：`v2/api/app.py:119`, `v2/api/app.py:520`; 对照 `v2/services/*/app.py`
- 问题：API 健康检查固定请求各服务 `/health`，但各服务未实现 `/health`。
- 影响：`/api/v1/system/status` 中服务几乎总是 `disconnected`（误报）。
- 建议：
  - 各服务增加 `/health`。
  - 或改为探测实际存在的版本化端点。

### H4. Artifact 元数据持续追加，查询非确定，LRU 统计失真
- 位置：`v2/db/repo.py:58`, `v2/db/repo.py:77`, `v2/services/fetch/service.py:193`, `v2/services/parse/service.py:49`, `v2/foundation/lru.py:10`
- 问题：
  - `upsert_artifact()` 使用随机 `artifact_id`，实际是 append，不是 upsert。
  - `get_artifact().first()` 无排序，返回不确定。
  - 多条记录可指向同一路径，LRU 按行累计 `size_bytes`，会重复计量。
- 影响：
  - 读取到旧记录、缓存行为随机。
  - LRU 可能过度淘汰或统计不准。
- 建议：
  - 对 `(paper_uid, artifact_type, parser_method, parser_version, evicted=0)` 建唯一约束或逻辑唯一。
  - `get_artifact` 明确按 `last_accessed_at desc` 或 `created_at desc`。
  - LRU 以“物理文件去重”计算容量。

### H5. API 层与“统一错误响应格式”契约不一致
- 位置：`v2/contracts/common.py:9`, `v2/services/parse/app.py:24`, `v2/services/analyze/app.py:25`, `v2/services/research/app.py:30`, `v2/services/daily_report/app.py:39`
- 问题：多处直接返回字符串 detail 或结构不一致。
- 影响：前端与调用方难以稳定处理错误。
- 建议：统一错误模型 `{code, message, details, trace_id}` 并在全局异常处理中落地。

### H6. “可追溯”承诺未落实：`service_call_logs` 未被写入
- 位置：`v2/db/models.py:193`，全仓未发现写入逻辑
- 问题：虽建表但无记录实现。
- 影响：无法按 trace_id 回溯服务调用输入摘要/输出摘要/耗时。
- 建议：在 API 编排点增加统一 service call logging 中间层或 helper。

## 4. 中优先级问题（Medium）

### M1. 去重算法复杂度高，规模上升后性能明显退化
- 位置：`v2/services/fetch/dedup.py:25`
- 问题：每条 incoming 都 `session.query(Paper).all()` 全表扫描。
- 影响：搜索落库呈 O(N*M)，数据量上来后明显变慢。
- 建议：
  - DOI、(year,title,first_author) 建索引并改为条件查询。
  - 预归一化字段避免 Python 全表循环。

### M2. 反馈读取路径全量扫描，不可扩展
- 位置：`v2/db/repo.py:117`, `v2/api/app.py:229`, `v2/api/app.py:244`
- 问题：列表/详情请求频繁触发 `latest_feedback_map()` 全量读取。
- 影响：论文与反馈量增大后接口性能下降。
- 建议：
  - 用子查询/窗口函数按 `paper_uid` 取最新反馈。
  - 或维护物化“latest feedback”表。

### M3. 多源搜索分页语义不正确
- 位置：`v2/services/fetch/service.py:35`
- 问题：`page/page_size` 被逐源独立执行并拼接，返回量可能 > `page_size` 且跨源无统一排序。
- 影响：前端分页与用户预期不一致。
- 建议：统一聚合后再全局排序+分页；返回 `total`/`has_more` 语义。

### M4. 设置输入缺少校验，存在无效配置写入风险
- 位置：`v2/api/app.py:498`, `v2/api/settings_runtime.py:37`
- 问题：`PUT /settings` 接受任意 dict，未做 schema/范围验证。
- 影响：负值、异常类型可入库，后续运行异常。
- 建议：用 Pydantic SettingsUpdateRequest（边界 + 类型 + 默认）。

### M5. `parse/analyze` 接口 path 与 body 的 `paper_uid` 重复且不一致时未校验
- 位置：`v2/api/app.py:307`, `v2/api/app.py:337`, `v2/contracts/parse.py:6`, `v2/contracts/analyze.py:6`
- 问题：路径参数才是真正使用值，body 中 `paper_uid` 实际被忽略。
- 影响：API 契约含糊，调用端容易误用。
- 建议：二选一：
  - 去掉 body 中 `paper_uid`；
  - 或强校验 path/body 必须一致。

### M6. 独立日报服务端点未完整使用请求参数
- 位置：`v2/services/daily_report/app.py:24`
- 问题：调用 `service.generate()` 时遗漏 `window_days` 与 `arxiv_categories`。
- 影响：service 直连场景行为与 API/BFF 场景不一致。
- 建议：按契约完整透传参数。

### M7. 前端存在不可达页面代码（路由未挂载）
- 位置：`frontend/src/features/recommendations/RecommendationsPage.tsx`, `frontend/src/features/tasks/TasksPage.tsx`, `frontend/src/app/router.tsx:15`
- 问题：页面实现存在但路由未注册。
- 影响：代码冗余、维护成本增加。
- 建议：删除或接入导航并补测试。

### M8. 后端/前端默认端口与文档不一致
- 位置：`start_server.sh:11`, `docs/V2_RUNBOOK.md:7`, `docs/V2_FRONTEND.md:15`
- 问题：`start_server.sh` 默认后端 `8011`，文档多处默认 `8001`。
- 影响：部署/联调易混淆。
- 建议：统一默认端口并在文档明确区分脚本模式。

### M9. `.env.example` 仍是旧版变量，误导配置
- 位置：`.env.example:1`
- 问题：主要是旧 `DATABASE_URL` / `LOG_*` / `FETCH_*` 等，不对应 V2 `V2_*`。
- 影响：新环境初始化容易失败或行为偏差。
- 建议：更新为 V2 权威变量集并删除旧字段。

### M10. 文档测试说明与实际测试集不一致
- 位置：`docs/V2_TESTING.md:1`
- 问题：文档仅列 2 类测试，实际已含更多回归与 live 测试。
- 影响：测试策略不可见，交接风险。
- 建议：同步更新测试矩阵（单元/集成/live、触发条件、耗时分层）。

## 5. 低优先级问题（Low）

### L1. 文件读取未使用上下文管理器
- 位置：`v2/services/daily_report/service.py:133`
- 建议：改为 `with open(...) as f:`。

### L2. worker 清理队列对坏行缺乏容错
- 位置：`v2/worker/runner.py:17`
- 问题：`json.loads` 异常会中断整个任务。
- 建议：坏行跳过并记录。

### L3. 前端主包体积过大，首屏性能风险
- 证据：`npm run build` 输出 `dist/assets/index-*.js 1357.74 kB`
- 建议：按页面懒加载路由 + 手动拆包。

## 6. 设计原则冲突汇总

### 6.1 分层/微服务边界冲突
- 文档宣称服务间 HTTP 编排，但 BFF 直接 new 服务类并本地调用：`v2/api/app.py:52`。
- 这使 `FETCH_SERVICE_URL` 等运行配置弱化为“仅健康检查用途”。

### 6.2 无状态与任务可靠性冲突
- 任务执行依赖进程内线程与同步阻塞，不是持久 worker 消费。

### 6.3 契约优先冲突
- 错误模型不统一，部分响应未遵循 contracts。
- 推荐 breakdown 字段与契约不一致：`recommended_inverse` 在 `service` 输出但 `contracts/recommend.py` 未定义。

### 6.4 可追溯性冲突
- `service_call_logs` 未落地，trace 仅部分字段写在 `jobs`。

## 7. 测试覆盖缺口
- 缺少“跨源 DOI 去重后 UID 一致性”回归测试。
- 缺少“settings 修改后立即影响 OCR/research timeout/timezone”的验证。
- 缺少 `papers/search` 异常路径 job 状态回写测试。
- 缺少健康检查端点一致性测试（`/health`）。
- 缺少 artifact 多版本/重复记录下 `get_artifact` 与 LRU 正确性测试。
- 缺少 service_call_logs 追踪测试。

## 8. 建议修复优先级（执行顺序）
1. 修复去重 UID 不变量与 source link 映射（C1）。
2. 重构 DB session 生命周期为 per-request（C2）。
3. 统一任务执行模型（入库 + worker）替换线程/阻塞调用（C3）。
4. 打通“设置即时生效”路径，移除静态 config 假象（H1）。
5. 统一错误模型与追踪日志（H5/H6）。
6. 修复 artifact 唯一性和检索确定性（H4）。
7. 补齐分页语义与性能优化（M1/M2/M3）。
8. 收敛文档与配置（M8/M9/M10）。

## 9. 附：本次静态审查已确认的质量现状
- 正向：核心主流程与现有测试可通过，端到端链路具备最小可用性。
- 风险：多为“规模化/并发/可靠性/一致性”问题，短期不一定暴露，长期会演化为高代价故障。
