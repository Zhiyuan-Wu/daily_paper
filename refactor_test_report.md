# Refactor & Real-Data Test Report

## 1. 执行时间与范围
- 执行日期: 2026-03-01
- 项目: `daily_paper` V2 backend
- 覆盖服务: fetch / parse / analyze / recommend / daily_report / research（含 API 编排层）
- 测试要求: 使用真实外部数据进行验证（OpenAlex + 真实 PDF 下载 + Claude CLI 调研）

## 2. 真实数据验证结果

### 2.1 手工真实链路验证（API + 真实数据）
执行结果（关键输出）:
- `search_status 200 items 20`
- `picked_external_id W3137278571`
- `parse_char_count 65091`
- `analyze_status 200`
- `recommend_status 200`
- `daily_status 200`
- `daily_get_status 200`
- `research_create_status 200 task_status completed`
- `research_result_status 200 sources_count 10 report_len 9378`

结论:
- 论文获取、解析、分析、推荐、日报、深度调研链路均已使用真实数据跑通。

### 2.2 自动化测试（真实数据）
执行命令与结果:
- `V2_RUN_LIVE_TESTS=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_openalex_fetch_parse_analyze_recommend_daily_report -s`
  - 结果: `1 passed`
- `V2_RUN_LIVE_RESEARCH=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_research_task_with_claude_cli -s`
  - 结果: `1 passed`
- `V2_RUN_LIVE_TESTS=1 V2_RUN_LIVE_RESEARCH=1 pytest -q tests_v2`
  - 结果: `7 passed`

## 3. 发现的问题与修复

### 问题 A: 日报生成在单篇论文下载失败时直接整体失败
- 复现现象: `DAILY_REPORT_FAILED`，下载某些链接返回 `403`，日报立即失败。
- 根因:
  - `daily_report` 在下载/解析环节对单篇失败无容错，异常直接冒泡。
  - OpenAlex 结果中可能存在不可直链下载或被站点拦截的链接。
- 修复:
  - `v2/services/daily_report/service.py`
  - 改为逐篇容错：单篇下载/解析失败时继续尝试下一篇；当且仅当没有任何可解析论文时才返回 `REPORT_PARSE_EMPTY`。

### 问题 B: fetch 把非 PDF 内容当 PDF 使用，导致后续解析失败
- 根因:
  - OpenAlex 插件可能把 `landing_page_url`（HTML）作为 `pdf_url`。
  - 下载后未校验内容是否真为 PDF。
- 修复:
  - `v2/services/fetch/plugins.py`
    - 仅优先选择明确的 `pdf_url`；仅在路径直接以 `.pdf` 结尾时才使用 landing URL 兜底。
  - `v2/services/fetch/service.py`
    - 增加请求异常处理（403/超时等）并标记 `pdf_unavailable=True`，不再直接抛 500。
    - 增加 PDF 内容校验（`Content-Type` 或 `%PDF-` 文件头）。

### 问题 C: research 在 `sources.json` 结构不稳定时失败
- 复现现象: `"'str' object has no attribute 'get'"`，任务状态 `failed`。
- 根因:
  - `sources.json` 实际可能是 dict 包装、字符串条目、或 markdown fenced json；旧实现只支持 `list[dict]`。
- 修复:
  - `v2/services/research/service.py`
  - 新增 `_read_sources_file` + `_coerce_source_list`，支持:
    - `[{...}]`
    - `{"sources": [...]}` / `{"items": [...]}` / `{"references": [...]}`
    - markdown 的 ```json ... ``` 块
    - 字符串条目兜底
  - `normalize` 增强为兼容 `str` / 非 dict 输入。

## 4. 新增与更新测试

### 新增真实功能测试
- `tests_v2/test_v2_live_real_data.py`
  - `test_live_openalex_fetch_parse_analyze_recommend_daily_report`
    - 真实 OpenAlex 搜索
    - 真实 PDF 导入 + parse
    - analyze + feedback + recommend
    - daily report 真实生成与查询
  - `test_live_research_task_with_claude_cli`
    - 真实 Claude CLI 调研任务创建与结果拉取

### 新增回归测试（快速）
- `tests_v2/test_v2_research_sources_parsing.py`
  - 锁定 `sources.json` 多种结构兼容逻辑，防止 research 再次因结构变化失败。

### 更新现有 e2e
- `tests_v2/test_v2_e2e.py`
  - 让 `report_service` 复用 monkeypatch 后的 `fetch_service`，保持测试稳定性。

### 测试标记与配置
- `pytest.ini`
  - 新增 `live`、`live_research` marker。
- `.gitignore`
  - 为关键测试文件添加白名单（`tests_v2/test_v2_e2e.py`、`tests_v2/test_v2_live_real_data.py`、`tests_v2/test_v2_research_sources_parsing.py`），确保新增测试可进入例行控制。

## 5. 本地例行执行建议
- 快速回归（默认，不跑真实外部依赖）:
  - `pytest -q tests_v2`
- 真实外部数据回归（推荐日常/定时）:
  - `V2_RUN_LIVE_TESTS=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_openalex_fetch_parse_analyze_recommend_daily_report`
- 真实 research 回归（需要 Claude CLI 可用与登录态）:
  - `V2_RUN_LIVE_RESEARCH=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_research_task_with_claude_cli`
- 全量（含 live）:
  - `V2_RUN_LIVE_TESTS=1 V2_RUN_LIVE_RESEARCH=1 pytest -q tests_v2`

## 6. 当前状态
- 后端关键真实功能已完成端到端验证并可用。
- 真实数据测试已写入 `tests_v2`，可用于例行质量控制。
