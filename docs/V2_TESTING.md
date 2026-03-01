# V2 测试说明

运行 V2 测试：

```bash
pytest -q tests_v2
```

测试覆盖：
- `test_v2_e2e.py`：端到端主流程（搜索→导入→解析→分析→推荐→调研→日报→设置）
- `test_v2_lru_and_worker.py`：双阈值 LRU 与清理重试逻辑
