# V2 测试说明

## 1. 快速回归
```bash
pytest -q tests_v2
```

当前默认套件覆盖：
- `test_v2_e2e.py`：端到端主流程（搜索→导入→解析→分析→推荐→调研→日报→设置）
- `test_v2_async_report_api.py`：异步日报任务状态流
- `test_v2_lazy_loading.py`：PDF/解析/分析懒加载链路
- `test_v2_fetch_service_search.py`：多源检索容错
- `test_v2_fetch_plugins.py`：OpenAlex 查询参数协议
- `test_v2_recommendation_count.py`：推荐次数反向策略
- `test_v2_report_defaults.py`：日报默认参数契约
- `test_v2_dashboard_api.py`：设置/状态/源可用性接口
- `test_v2_lru_and_worker.py`：LRU 与清理队列重试
- `test_v2_research_sources_parsing.py`：`sources.json` 结构兼容
- `test_v2_dedup_uid_consistency.py`：跨源去重后 UID 一致性与下载解析可用性
- `test_v2_job_failure_and_logs.py`：失败任务状态回写 + `service_call_logs` 追踪
- `test_v2_runtime_settings_effect.py`：设置保存后参数对新请求即时生效（OCR 超时）

## 2. 真实外部数据测试（可选）
```bash
V2_RUN_LIVE_TESTS=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_openalex_fetch_parse_analyze_recommend_daily_report
```

## 3. 真实调研测试（可选，依赖 Claude CLI）
```bash
V2_RUN_LIVE_RESEARCH=1 pytest -q tests_v2/test_v2_live_real_data.py::test_live_research_task_with_claude_cli
```

## 4. 建议策略
- 开发阶段：执行第 1 节（快速回归）
- 交付前：执行第 1 节 + 第 2 节
- 发布前：执行第 1 节 + 第 2 节 + 第 3 节
