# 日志系统使用说明

## 概述

Daily Paper系统使用统一的日志配置，所有模块的日志都会输出到文件中，便于调试和监控。

## 日志配置

### 环境变量

在 `.env` 文件中配置以下变量：

```bash
# 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# 日志文件目录
LOG_DIR=data/logs

# 日志文件名
LOG_FILE=daily_paper.log

# 单个日志文件最大大小（字节）- 默认10MB
LOG_MAX_BYTES=10485760

# 保留的备份文件数量
LOG_BACKUP_COUNT=5

# 日志格式
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# 日期格式
LOG_DATE_FORMAT=%Y-%m-%d %H:%M:%S

# 是否同时输出到控制台
LOG_CONSOLE_OUTPUT=true
```

### 日志级别说明

- **DEBUG**: 详细的调试信息，通常只在开发时使用
- **INFO**: 一般信息，记录正常的操作流程
- **WARNING**: 警告信息，表示可能出现问题
- **ERROR**: 错误信息，表示操作失败
- **CRITICAL**: 严重错误，可能导致程序无法继续运行

## 日志文件

### 位置

默认日志文件位置：`data/logs/daily_paper.log`

### 日志轮转

当日志文件达到 `LOG_MAX_BYTES` 指定的大小时，会自动进行轮转：

- 当前日志文件：`daily_paper.log`
- 备份1：`daily_paper.log.1`
- 备份2：`daily_paper.log.2`
- ...
- 最多保留 `LOG_BACKUP_COUNT` 个备份文件

旧日志文件会被自动删除，确保磁盘空间不会无限增长。

## 使用方法

### 在代码中配置日志

#### 1. FastAPI应用（backend/main.py）

```python
import logging
from daily_paper.config import Config
from daily_paper.logging_config import setup_logging

# 在应用启动时配置日志
config = Config.from_env()
setup_logging(config.log)

# 获取logger
logger = logging.getLogger(__name__)
logger.info("Application started")
```

#### 2. 独立脚本（如demo脚本）

```python
import logging
from daily_paper.config import Config
from daily_paper.logging_config import setup_logging

# 首先配置日志
config = Config.from_env()
setup_logging(config.log)

# 然后导入其他模块
from daily_paper.parsers import PDFParser

logger = logging.getLogger(__name__)
logger.info("Script started")
```

#### 3. 在任何模块中使用

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### 查看日志

#### 实时查看日志

```bash
# Linux/Mac
tail -f data/logs/daily_paper.log

# 或使用colored tail（如果已安装）
ccze -A < data/logs/daily_paper.log
```

#### 查看最近100行

```bash
tail -n 100 data/logs/daily_paper.log
```

#### 搜索特定内容

```bash
# 搜索错误
grep "ERROR" data/logs/daily_paper.log

# 搜索特定模块
grep "daily_paper.parsers" data/logs/daily_paper.log

# 搜索今天的日志
grep "$(date +%Y-%m-%d)" data/logs/daily_paper.log
```

## 日志格式

每条日志的格式如下：

```
2026-01-18 23:33:50 - daily_paper.parsers.pdf_parser - INFO - PyMuPDF extraction successful
│                    │                            │       └─ 消息内容
│                    │                            └─ 日志级别
│                    └─ 模块名称
└─ 时间戳
```

## 高级用法

### 临时修改日志级别

在不修改配置的情况下临时修改某个模块的日志级别：

```python
import logging

# 将parser模块的日志级别改为DEBUG
logging.getLogger('daily_paper.parsers').setLevel(logging.DEBUG)
```

### 使用上下文管理器

使用 `ContextualLogger` 临时修改日志级别：

```python
from daily_paper.logging_config import ContextualLogger

# 在特定代码块中启用DEBUG日志
with ContextualLogger('daily_paper.parsers', level='DEBUG'):
    # 这里的日志会以DEBUG级别输出
    parser.parse(paper)  # paper is a Paper object with pdf_path attribute
# 日志级别恢复原状
```

### 不同模块使用不同级别

```python
import logging

# 设置parser模块为DEBUG
logging.getLogger('daily_paper.parsers').setLevel(logging.DEBUG)

# 设置其他模块保持INFO
logging.getLogger('daily_paper').setLevel(logging.INFO)
```

## 性能考虑

1. **生产环境建议使用 INFO 或 WARNING 级别**：DEBUG 级别会产生大量日志，影响性能

2. **异步日志**：当前使用同步写入，对于高并发场景，可以考虑使用异步日志库如 `loguru`

3. **合理设置轮转大小**：过小的文件会导致频繁轮转，过大的文件会影响查看性能

## 故障排查

### 日志文件未创建

检查以下几点：

1. 日志目录是否存在且有写权限
   ```bash
   ls -la data/logs
   ```

2. `.env` 文件中的 `LOG_DIR` 配置是否正确

3. 应用是否有权限写入日志目录

### 日志未输出到文件

1. 确认 `setup_logging()` 在应用启动时被调用
2. 检查日志级别设置是否过高（如设置为ERROR，INFO日志不会输出）
3. 确认没有其他代码修改了root logger的配置

## 示例

### 完整的FastAPI应用日志配置示例

```python
# backend/main.py
import logging

from daily_paper.config import Config
from daily_paper.logging_config import setup_logging

# 配置日志（必须在其他导入之前）
config = Config.from_env()
setup_logging(config.log)

logger = logging.getLogger(__name__)

from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up...")

@app.get("/")
async def root():
    logger.debug("Root endpoint called")
    return {"message": "Hello"}

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI application shutting down...")
```

### 完整的独立脚本日志配置示例

```python
#!/usr/bin/env python3
import logging
from daily_paper.config import Config
from daily_paper.logging_config import setup_logging

# 配置日志
config = Config.from_env()
setup_logging(config.log)
logger = logging.getLogger(__name__)

def main():
    logger.info("Script started")

    try:
        # 你的代码
        result = do_something()
        logger.info(f"Operation completed: {result}")
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
```

## 更多资源

- Python logging文档：https://docs.python.org/3/library/logging.html
- RotatingFileHandler文档：https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler
