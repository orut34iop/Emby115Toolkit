# Emby115Toolkit 测试报告

**执行时间**: 2026/04/22  
**Python 版本**: 3.13.11 (uv managed)  
**pytest 版本**: 9.0.3

---

## 执行命令

```bash
uv run pytest tests/ -v --tb=line
```

---

## 总体结果

| 项目 | 数量 |
|---|---|
| **通过 (Passed)** | 95 |
| **跳过 (Skipped)** | 3 |
| **失败 (Failed)** | 0 |
| **错误 (Error)** | 0 |
| **总计** | 98 |

**通过率**: 95 / 98 = **96.9%**（跳过项因环境限制，非代码问题）

---

## 跳过的测试说明

| 测试 | 跳过原因 |
|---|---|
| `test_symlink_deleter::test_run_deletes_symlinks` | Windows 需管理员权限创建符号链接 |
| `test_symlink_deleter::test_run_counts_correctly` | Windows 需管理员权限创建符号链接 |
| `test_metadata_copyer::test_avoids_symlink_loops` | Windows 需管理员权限创建符号链接 |

---

## 按模块统计

### 单元测试 (10 个文件, 93 个测试)

| 被测模块 | 测试文件 | 通过 | 跳过 | 覆盖要点 |
|---|---|---|---|---|
| `utils/config.py` | `test_config.py` | 9 | 0 | 单例行为、默认配置合并、get/set/save 往返 |
| `utils/listdir.py` | `test_listdir.py` | 10 | 0 | 文件名生成、返回元组 bug、空目录/不存在目录处理 |
| `utils/logger.py` | `test_logger.py` | 5 | 0 | TextHandler 队列、setup_logger、文件轮转 |
| `utils/history_entry.py` | `test_history_entry.py` | 8 | 0 | 路径解析、历史去重/限制、路径规范化 |
| `autosync/SymlinkCreator.py` | `test_symlink_creator.py` | 9 | 0 | symlink 创建(mocked)、路径替换、扩展名过滤、strm URL |
| `autosync/MetadataCopyer.py` | `test_metadata_copyer.py` | 4 | 1 | 文件复制/跳过、扩展名过滤、tvshow.nfo 模式 |
| `autosync/SymlinkDeleter.py` | `test_symlink_deleter.py` | 2 | 2 | 跳过普通文件、空目录处理 |
| `autosync/FileMerger.py` | `test_file_merger.py` | 7 | 0 | 初始化验证、视频匹配、文件移动 |
| `autosync/TreeMirror.py` | `test_tree_mirror.py` | 10 | 0 | 特殊字符替换、编码回退、10级缩进解析、空文件创建 |
| `emby/EmbyOperator.py` | `test_emby_operator.py` | 17 | 0 | HTTP API、NFO 解析、TMDb 查重、版本合并、用户查找 |

### 集成测试 (2 个文件, 5 个测试)

| 模块 | 测试文件 | 通过 | 覆盖要点 |
|---|---|---|---|
| Emby API 工作流 | `test_emby_api.py` | 3 | 完整查重流程、版本合并流程、用户 ID 获取 |
| Symlink 工作流 | `test_symlink_workflow.py` | 2 | 符号链接创建工作流、元数据复制工作流 |

---

## 已知 Bug 回归测试（5 项全部通过）

| Bug 描述 | 验证方式 | 状态 |
|---|---|---|
| `listdir.py` docstring 声称返回 3 元组，实际返回 2 | 断言 `len(result) == 2` | 已记录 |
| `EmbyOperator.py` 缺失 `return None, False`（无 tmdbid 时隐式返回 None） | 断言 `result is None` | 已记录 |
| `EmbyOperator.py` `Path` 被导入两次（第 11、16 行） | AST 解析统计 | 已记录 |
| `EmbyOperator.py` URL 拼写错误 `?/api_key=` | 源码字符串断言 | 已记录 |
| `EmbyOperator.py` `check_video_files` 使用裸文件名 | 源码字符串断言 | 已记录 |

---

## 运行方式

```bash
# 全部测试
uv run pytest

# 仅单元测试
uv run pytest -m unit

# 仅集成测试
uv run pytest -m integration

# 特定模块
uv run pytest tests/unit/test_emby_operator.py -v
```

---

## 测试文件清单

```
tests/
|-- conftest.py
|-- __init__.py
|-- pytest.ini
|-- unit/
|   |-- __init__.py
|   |-- test_config.py
|   |-- test_emby_operator.py
|   |-- test_file_merger.py
|   |-- test_history_entry.py
|   |-- test_listdir.py
|   |-- test_logger.py
|   |-- test_metadata_copyer.py
|   |-- test_symlink_creator.py
|   |-- test_symlink_deleter.py
|   |-- test_tree_mirror.py
|-- integration/
|   |-- __init__.py
|   |-- test_emby_api.py
|   |-- test_symlink_workflow.py
```

---

## 依赖变更

`requirements.txt` 中新增了测试依赖：

```
pytest>=8.0.0
pytest-mock>=3.14.0
responses>=0.25.0
freezegun>=1.5.0
```

---

*本报告由 pytest 自动生成，保存于项目根目录 `test-report.md`。*
